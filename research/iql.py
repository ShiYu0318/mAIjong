"""Discrete IQL prototype: data-action twin Q, expectile V, masked AWR actor.

Reference: Kostrikov et al., arXiv:2110.06169, equations 5--7.
This is an experimental local trainer, not a promoted production policy.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path

import torch
from torch import nn

from ai.agents.neural_agent import save_checkpoint
from ai.models.backbone import LATENT
from ai.models.ppo_model import ActorCritic


def expectile_loss(residual: torch.Tensor, tau: float) -> torch.Tensor:
    if not 0 < tau < 1:
        raise ValueError('tau must be strictly between zero and one')
    return (torch.where(residual >= 0, tau, 1 - tau) * residual.square()).mean()


@torch.no_grad()
def bellman_target(reward: torch.Tensor, done: torch.Tensor, next_value: torch.Tensor,
                   gamma: float) -> torch.Tensor:
    # where also excludes terminal NaNs; multiplication by zero alone would not.
    return reward + gamma * torch.where(done, torch.zeros_like(next_value), next_value)


def min_data_q(q1: torch.Tensor, q2: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
    return torch.minimum(q1.gather(1, actions[:, None]),
                         q2.gather(1, actions[:, None])).squeeze(1)


@torch.no_grad()
def advantage_weights(q: torch.Tensor, value: torch.Tensor, beta: float,
                      max_weight: float) -> torch.Tensor:
    if beta < 0 or max_weight <= 0:
        raise ValueError('beta must be nonnegative and max_weight positive')
    return (beta * (q - value)).clamp(max=math.log(max_weight)).exp()


class Critic(nn.Module):
    def __init__(self, actor: ActorCritic, outputs: int):
        super().__init__()
        self.encoder = copy.deepcopy(actor.encoder)
        self.head = nn.Sequential(nn.Linear(LATENT, 128), nn.ReLU(), nn.Linear(128, outputs))
        nn.init.zeros_(self.head[-1].weight)
        nn.init.zeros_(self.head[-1].bias)

    def forward(self, tiles, scalars):
        return self.head(self.encoder(tiles, scalars))


class IQLLearner:
    def __init__(self, actor: ActorCritic, tau: float = 0.7, beta: float = 1.0,
                 max_weight: float = 100.0, polyak: float = 0.005, gamma: float = 1.0,
                 critic_lr: float = 3e-4, actor_lr: float = 3e-5):
        if not (0 < tau < 1 and beta >= 0 and max_weight > 0 and 0 < polyak <= 1
                and 0 <= gamma <= 1 and critic_lr > 0 and actor_lr > 0):
            raise ValueError('Invalid IQL hyperparameters')
        if actor.use_history:
            raise ValueError('This first offline prototype requires a no-history actor')
        self.tau, self.beta, self.max_weight = tau, beta, max_weight
        self.polyak, self.gamma = polyak, gamma
        self.actor = copy.deepcopy(actor)
        self.reference = copy.deepcopy(actor).eval().requires_grad_(False)
        self.q1, self.q2 = Critic(actor, 108), Critic(actor, 108)
        self.value = Critic(actor, 1)
        self.q1_target = copy.deepcopy(self.q1).eval().requires_grad_(False)
        self.q2_target = copy.deepcopy(self.q2).eval().requires_grad_(False)
        self.q_opt = torch.optim.Adam([*self.q1.parameters(), *self.q2.parameters()],
                                      lr=critic_lr)
        self.v_opt = torch.optim.Adam(self.value.parameters(), lr=critic_lr)
        self.actor_opt = torch.optim.Adam(self.actor.parameters(), lr=actor_lr)

    @staticmethod
    def _step(loss, optimizer, parameters):
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, 1.0)
        optimizer.step()

    def update(self, batch: dict[str, torch.Tensor], train_actor: bool = True
               ) -> dict[str, float]:
        t, s = batch['tiles'], batch['scalars']
        actions, masks = batch['actions'], batch['masks']
        if not masks.gather(1, actions[:, None]).all():
            raise ValueError('Offline dataset action is illegal')
        with torch.no_grad():
            q_data = min_data_q(self.q1_target(t, s), self.q2_target(t, s), actions)
        value = self.value(t, s).squeeze(1)
        residual = q_data - value
        v_loss = expectile_loss(residual, self.tau)
        self._step(v_loss, self.v_opt, self.value.parameters())

        with torch.no_grad():
            next_value = self.value(batch['next_tiles'], batch['next_scalars']).squeeze(1)
            target = bellman_target(batch['rewards'], batch['done'], next_value, self.gamma)
        q1 = self.q1(t, s).gather(1, actions[:, None]).squeeze(1)
        q2 = self.q2(t, s).gather(1, actions[:, None]).squeeze(1)
        td1, td2 = q1 - target, q2 - target
        q_loss = (td1.square() + td2.square()).mean()
        self._step(q_loss, self.q_opt, [*self.q1.parameters(), *self.q2.parameters()])
        with torch.no_grad():
            for online, frozen in [(self.q1, self.q1_target), (self.q2, self.q2_target)]:
                for target_parameter, parameter in zip(frozen.parameters(), online.parameters(),
                                                       strict=True):
                    target_parameter.lerp_(parameter, self.polyak)
            weights = advantage_weights(q_data, self.value(t, s).squeeze(1),
                                         self.beta, self.max_weight)
        stats = {'q_loss': float(q_loss.detach()), 'v_loss': float(v_loss.detach()),
                 'q_mean': float(q_data.mean()), 'target_mean': float(target.mean()),
                 'expectile_positive_fraction': float((residual.detach() > 0).float().mean()),
                 'weight_mean': float(weights.mean()),
                 'weight_clip_fraction': float(
                     (weights >= self.max_weight * 0.99999).float().mean()),
                 'weight_ess_fraction': float(weights.sum().square()
                                               / (weights.square().sum() * len(weights) + 1e-12))}
        for name, chosen in [('terminal', batch['done']), ('nonterminal', ~batch['done'])]:
            if chosen.any():
                stats[name + '_td_rmse'] = float(td1.detach()[chosen].square().mean().sqrt())
        if train_actor:
            logp, _ = self.actor(t, s, masks)
            actor_loss = -(weights * logp.gather(1, actions[:, None]).squeeze(1)).mean()
            with torch.no_grad():
                ref_logp, _ = self.reference(t, s, masks)
                kl = (ref_logp.exp() * (ref_logp - logp).masked_fill(~masks, 0)).sum(1).mean()
            self._step(actor_loss, self.actor_opt, self.actor.parameters())
            stats.update(actor_loss=float(actor_loss.detach()), kl_to_initial=float(kl))
        return stats

    @torch.no_grad()
    def diagnostics(self, batch: dict[str, torch.Tensor]) -> dict[str, float]:
        t, s, actions = batch['tiles'], batch['scalars'], batch['actions']
        q = min_data_q(self.q1(t, s), self.q2(t, s), actions)
        value = self.value(t, s).squeeze(1)
        next_value = self.value(batch['next_tiles'], batch['next_scalars']).squeeze(1)
        target = bellman_target(batch['rewards'], batch['done'], next_value, self.gamma)
        logp, _ = self.actor(t, s, batch['masks'])
        ref, _ = self.reference(t, s, batch['masks'])
        result = {'q_mean': float(q.mean()), 'value_mean': float(value.mean()),
                  'v_loss': float(expectile_loss(q - value, self.tau)),
                  'nll': float(-logp.gather(1, actions[:, None]).mean()),
                  'kl_to_initial': float((ref.exp() * (ref - logp).masked_fill(
                      ~batch['masks'], 0)).sum(1).mean())}
        for name, mask in [('terminal', batch['done']), ('nonterminal', ~batch['done'])]:
            if mask.any():
                result[name + '_td_rmse'] = float((q[mask] - target[mask]).square().mean().sqrt())
        return result

    def save_actor(self, path: Path, **metadata):
        config = {'hierarchical': self.actor.hierarchical,
                  'use_transformer': self.actor.encoder.use_transformer}
        save_checkpoint(path, self.actor, 'ppo', config, training_method='iql', **metadata)
