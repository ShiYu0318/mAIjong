"""PPO self-play fine-tuning (SPEC 05.6.2).

python -m ai.training.ppo_trainer --init checkpoints/bc_v1.pt --updates 200
"""

from __future__ import annotations

import argparse
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ai.agents.neural_agent import PolicyAgent, save_checkpoint
from ai.env import MahjongEnv
from ai.models.ppo_model import ActorCritic
from ai.training.evaluate import evaluate
from ai.training.metrics import MetricsLogger
from ai.training.self_play import League


@dataclass
class PPOConfig:
    n_envs: int = 8
    rollout_steps: int = 256  # per env per update
    updates: int = 200
    mini_batch: int = 512
    n_epochs: int = 4
    lr: float = 3e-4
    lr_min: float = 1e-5
    clip_eps: float = 0.2
    entropy_start: float = 0.01
    entropy_end: float = 0.001
    vf_coeff: float = 0.5
    gamma: float = 0.99
    gae_lambda: float = 0.95
    max_grad_norm: float = 0.5
    snapshot_every: int = 10
    eval_every: int = 20
    eval_hands: int = 100
    hierarchical: bool = True
    seed: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def _stack(obs: list[dict[str, np.ndarray]]) -> tuple[torch.Tensor, torch.Tensor]:
    return (torch.from_numpy(np.stack([o["tiles"] for o in obs])),
            torch.from_numpy(np.stack([o["scalars"] for o in obs])))


def _snapshot_factory(model: torch.nn.Module, model_config: dict[str, Any]
                      ) -> Callable[[int], PolicyAgent]:
    snap = ActorCritic(**model_config)
    snap.load_state_dict(model.state_dict())
    return lambda seed: PolicyAgent(snap, "ppo", 0.1, seed)


def masked_entropy(logp: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    p = logp.exp() * mask
    return -(p * logp.masked_fill(~mask, 0.0)).sum(dim=1)


def train_ppo(cfg: PPOConfig, out: Path, init: Path | None = None, run: str = "ppo"
              ) -> dict[str, float]:
    torch.manual_seed(cfg.seed)
    model_config = {"hierarchical": cfg.hierarchical, "use_transformer": False}
    model = ActorCritic(**model_config)
    if init is not None:
        state = torch.load(init, map_location="cpu", weights_only=False)["state_dict"]
        model.load_state_dict(state)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    league = League(model_config, seed=cfg.seed)
    league.add(model)
    logger = MetricsLogger(run, {"kind": "ppo", **cfg.__dict__, "init": str(init)})

    envs = [MahjongEnv(rotate_seat=True, seed=cfg.seed * 1000 + i) for i in range(cfg.n_envs)]
    obs, masks = [], []
    for e in envs:
        e.opponent_agents = league.opponents()
        o, info = e.reset()
        obs.append(o)
        masks.append(info["legal_mask"])

    last_eval: dict[str, float] = {}
    t0 = time.time()
    episodes, wins, rewards_sum = 0, 0, 0.0
    for update in range(1, cfg.updates + 1):
        frac = (update - 1) / max(1, cfg.updates - 1)
        lr = cfg.lr_min + 0.5 * (cfg.lr - cfg.lr_min) * (1 + math.cos(math.pi * frac))
        for g in opt.param_groups:
            g["lr"] = lr
        ent_coeff = cfg.entropy_start + (cfg.entropy_end - cfg.entropy_start) * frac

        keys = ("tiles", "scalars", "mask", "act", "logp", "val", "rew", "done")
        buf: dict[str, list[Any]] = {k: [] for k in keys}
        model.eval()
        for _ in range(cfg.rollout_steps):
            t, s = _stack(obs)
            m = torch.from_numpy(np.stack(masks))
            with torch.no_grad():
                logp, val = model(t, s, m)
                act = torch.distributions.Categorical(logits=logp).sample()
            buf["tiles"].append(t)
            buf["scalars"].append(s)
            buf["mask"].append(m)
            buf["act"].append(act)
            buf["logp"].append(logp.gather(1, act[:, None]).squeeze(1))
            buf["val"].append(val)
            rew, done = [], []
            for i, e in enumerate(envs):
                o, r, term, trunc, info = e.step(int(act[i]))
                rew.append(r)
                done.append(term or trunc)
                rewards_sum += r
                if term or trunc:
                    episodes += 1
                    res = info.get("result") or {}
                    wins += int(res.get("kind") == "HU" and res.get("winner") == info["seat"])
                    e.opponent_agents = league.opponents()
                    o, info = e.reset()
                obs[i] = o
                masks[i] = info["legal_mask"]
            buf["rew"].append(torch.tensor(rew, dtype=torch.float32))
            buf["done"].append(torch.tensor(done, dtype=torch.float32))

        # GAE over the rollout (per env column)
        with torch.no_grad():
            t, s = _stack(obs)
            _, next_val = model(t, s, torch.from_numpy(np.stack(masks)))
        T = cfg.rollout_steps
        vals = torch.stack(buf["val"])
        rews = torch.stack(buf["rew"])
        dones = torch.stack(buf["done"])
        adv = torch.zeros_like(rews)
        gae = torch.zeros(cfg.n_envs)
        for k in reversed(range(T)):
            nv = next_val if k == T - 1 else vals[k + 1]
            nonterm = 1.0 - dones[k]
            delta = rews[k] + cfg.gamma * nv * nonterm - vals[k]
            gae = delta + cfg.gamma * cfg.gae_lambda * nonterm * gae
            adv[k] = gae
        ret = adv + vals

        flat = {
            "tiles": torch.cat(buf["tiles"]), "scalars": torch.cat(buf["scalars"]),
            "mask": torch.cat(buf["mask"]), "act": torch.cat(buf["act"]),
            "logp": torch.cat(buf["logp"]), "val": vals.flatten(),
            "adv": adv.flatten(), "ret": ret.flatten(),
        }
        flat["adv"] = (flat["adv"] - flat["adv"].mean()) / (flat["adv"].std() + 1e-8)
        n = len(flat["act"])
        model.train()
        stats: list[tuple[float, float, float]] = []
        for _ in range(cfg.n_epochs):
            perm = torch.randperm(n)
            for i in range(0, n, cfg.mini_batch):
                b = perm[i:i + cfg.mini_batch]
                logp_all, v = model(flat["tiles"][b], flat["scalars"][b], flat["mask"][b])
                logp = logp_all.gather(1, flat["act"][b][:, None]).squeeze(1)
                ratio = (logp - flat["logp"][b]).exp()
                a = flat["adv"][b]
                clipped = ratio.clamp(1 - cfg.clip_eps, 1 + cfg.clip_eps)
                pg = -torch.min(ratio * a, clipped * a).mean()
                v_clip = flat["val"][b] + (v - flat["val"][b]).clamp(-cfg.clip_eps, cfg.clip_eps)
                vf = torch.max((v - flat["ret"][b]) ** 2, (v_clip - flat["ret"][b]) ** 2).mean()
                ent = masked_entropy(logp_all, flat["mask"][b]).mean()
                loss = pg + cfg.vf_coeff * vf - ent_coeff * ent
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.max_grad_norm)
                opt.step()
                stats.append((float(pg.detach()), float(vf.detach()), float(ent.detach())))

        var_y = float(flat["ret"].var())
        explained = 1 - float((flat["ret"] - flat["val"]).var()) / var_y if var_y > 0 else 0.0
        metrics: dict[str, float] = {
            "policy_loss": float(np.mean([x[0] for x in stats])),
            "value_loss": float(np.mean([x[1] for x in stats])),
            "entropy": float(np.mean([x[2] for x in stats])),
            "explained_variance": explained, "lr": lr,
            "episodes": float(episodes), "train_win_rate": wins / max(1, episodes),
            "mean_step_reward": rewards_sum / max(1, update * T * cfg.n_envs),
            "sps": update * T * cfg.n_envs / (time.time() - t0),
        }
        if update % cfg.snapshot_every == 0:
            league.add(model)
        if update % cfg.eval_every == 0 or update == cfg.updates:
            res = evaluate(_snapshot_factory(model, model_config), "rule", cfg.eval_hands)
            last_eval = res.as_dict()
            metrics.update(last_eval)
            save_checkpoint(out, model, "ppo", model_config, update=update, **last_eval)
        logger.log(update, **metrics)
    logger.close()
    return last_eval


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", type=Path, default=None, help="BC checkpoint to start from")
    ap.add_argument("--out", type=Path, default=Path("checkpoints/ppo_latest.pt"))
    ap.add_argument("--updates", type=int, default=200)
    ap.add_argument("--envs", type=int, default=8)
    ap.add_argument("--rollout", type=int, default=256)
    ap.add_argument("--eval-every", type=int, default=20)
    ap.add_argument("--run", default=f"ppo-{int(time.time())}")
    args = ap.parse_args()
    cfg = PPOConfig(n_envs=args.envs, rollout_steps=args.rollout, updates=args.updates,
                    eval_every=args.eval_every)
    print(train_ppo(cfg, args.out, args.init, args.run))


if __name__ == "__main__":
    main()
