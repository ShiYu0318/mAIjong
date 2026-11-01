"""Ordinary-MSE Monte Carlo critic initialization, before standard IQL updates."""
from __future__ import annotations

import numpy as np
import torch


def monte_carlo_returns(data: dict[str, np.ndarray], gamma: float = 1.0) -> np.ndarray:
    """One source shard only: identical seeds from different opponents must not merge."""
    if not 0 <= gamma <= 1:
        raise ValueError('gamma must be between zero and one')
    n = len(data['rewards'])
    if not n or any(len(data[key]) != n for key in
                    ['hand_seeds', 'seats', 'decision_index', 'done']):
        raise ValueError('Nonempty aligned trajectories required')
    if not np.isfinite(data['rewards']).all():
        raise ValueError('Rewards must be finite')
    trajectories = {}
    for i, (seed, seat) in enumerate(zip(data['hand_seeds'], data['seats'], strict=True)):
        trajectories.setdefault((int(seed), int(seat)), []).append(i)
    result = np.empty(n, dtype=np.float32)
    for indices in trajectories.values():
        indices.sort(key=lambda i: data['decision_index'][i])
        if [int(data['decision_index'][i]) for i in indices] != list(range(len(indices))):
            raise ValueError('Duplicate or incomplete decision sequence; check source grouping')
        terminal = data['done'][indices]
        if not terminal[-1] or terminal[:-1].any():
            raise ValueError('Trajectory must have exactly one terminal at its end')
        value = 0.0
        for i in reversed(indices):
            value = float(data['rewards'][i]) + gamma * value
            result[i] = value
    return result


def warm_start_critics(learner, data: dict[str, torch.Tensor], updates: int = 300,
                      batch_size: int = 128, seed: int = 0, log=None):
    """Fit behavior-return means; do not use expectile loss on lucky MC outcomes.

    This initializes critics, never changes the actor. Subsequent IQL must still
    use expectile Q-derived values and ordinary TD backups, not these MC labels.
    """
    rng = np.random.default_rng(seed)
    stats = {}
    for step in range(1, updates + 1):
        ids = rng.integers(len(data['actions']), size=batch_size)
        t, s, a = data['tiles'][ids], data['scalars'][ids], data['actions'][ids]
        target = data['mc_returns'][ids]
        q1 = learner.q1(t, s).gather(1, a[:, None]).squeeze(1)
        q2 = learner.q2(t, s).gather(1, a[:, None]).squeeze(1)
        q_loss = ((q1 - target).square() + (q2 - target).square()).mean()
        learner._step(q_loss, learner.q_opt,
                      [*learner.q1.parameters(), *learner.q2.parameters()])
        value = learner.value(t, s).squeeze(1)
        v_loss = (value - target).square().mean()
        learner._step(v_loss, learner.v_opt, learner.value.parameters())
        stats = {'step': step, 'mc_q_loss': float(q_loss.detach()),
                 'mc_value_loss': float(v_loss.detach())}
        if log is not None and step % 50 == 0:
            log(stats)
    learner.q1_target.load_state_dict(learner.q1.state_dict())
    learner.q2_target.load_state_dict(learner.q2.state_dict())
    return stats
