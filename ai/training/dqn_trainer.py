"""Dueling double DQN with n-step returns and prioritized replay (SPEC 05.6.3–05.6.5).

python -m ai.training.dqn_trainer --steps 200000
"""

from __future__ import annotations

import argparse
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ai.agents.neural_agent import PolicyAgent, save_checkpoint
from ai.env import MahjongEnv
from ai.models.dqn_model import DuelingDQN
from ai.simulate import make_agent
from ai.training.evaluate import evaluate
from ai.training.metrics import MetricsLogger
from ai.training.replay_buffer import PrioritizedReplayBuffer


@dataclass
class DQNConfig:
    steps: int = 200_000
    buffer: int = 200_000
    batch: int = 256
    lr: float = 1e-4
    gamma: float = 0.99
    n_step: int = 5
    alpha: float = 0.6
    beta_start: float = 0.4
    beta_steps: int = 1_000_000
    train_every: int = 4
    target_every: int = 1000
    warmup: int = 5_000
    eps_start: float = 1.0
    eps_mid_step: int = 50_000
    eps_end_step: int = 200_000
    eps_floor: float = 0.05
    noisy: bool = False
    opponent: str = "rule:1.5"
    eval_every: int = 20_000
    eval_hands: int = 100
    seed: int = 0


def epsilon(step: int, c: DQNConfig) -> float:
    """1.0 until eps_mid_step, then linear to 0.1 by eps_end_step, then the floor."""
    if c.noisy:
        return 0.0
    if step < c.eps_mid_step:
        return c.eps_start
    if step < c.eps_end_step:
        f = (step - c.eps_mid_step) / (c.eps_end_step - c.eps_mid_step)
        return c.eps_start + (0.1 - c.eps_start) * f
    return c.eps_floor


def train_dqn(c: DQNConfig, out: Path, run: str = "dqn") -> dict[str, float]:
    torch.manual_seed(c.seed)
    rng = np.random.default_rng(c.seed)
    model_config = {"noisy": c.noisy, "use_transformer": False}
    online, target = DuelingDQN(**model_config), DuelingDQN(**model_config)
    target.load_state_dict(online.state_dict())
    opt = torch.optim.Adam(online.parameters(), lr=c.lr)
    buf = PrioritizedReplayBuffer(c.buffer, c.alpha)
    logger = MetricsLogger(run, {"kind": "dqn", **c.__dict__})
    env = MahjongEnv(rotate_seat=True, seed=c.seed,
                     opponent_agents=[make_agent(c.opponent, c.seed + i) for i in range(3)])
    obs, info = env.reset()
    pending: deque[tuple[Any, ...]] = deque()
    losses: list[float] = []
    last_eval: dict[str, float] = {}
    episodes = 0
    t0 = time.time()

    def tensors(o: dict[str, np.ndarray]) -> tuple[torch.Tensor, torch.Tensor]:
        return torch.from_numpy(o["tiles"])[None], torch.from_numpy(o["scalars"])[None]

    for step in range(1, c.steps + 1):
        mask = info["legal_mask"]
        if rng.random() < epsilon(step, c):
            action = int(rng.choice(np.flatnonzero(mask)))
        else:
            with torch.no_grad():
                q = online(*tensors(obs))[0].masked_fill(~torch.from_numpy(mask), float("-inf"))
            action = int(q.argmax())
        nobs, r, term, trunc, ninfo = env.step(action)
        done = term or trunc
        pending.append((obs, mask, action, r))
        # emit n-step transitions
        while len(pending) >= c.n_step or (done and pending):
            o0, m0, a0, _ = pending[0]
            ret = sum(c.gamma ** k * pending[k][3] for k in range(len(pending)))
            buf.add((o0, a0, ret, nobs, ninfo["legal_mask"], float(done),
                     c.gamma ** len(pending)))
            pending.popleft()
            if not done:
                break
        if done:
            episodes += 1
            obs, info = env.reset()
        else:
            obs, info = nobs, ninfo

        if step >= c.warmup and step % c.train_every == 0 and len(buf) >= c.batch:
            beta = min(1.0, c.beta_start + (1 - c.beta_start) * step / c.beta_steps)
            batch = buf.sample(c.batch, beta, rng)
            o, a, ret, no, nmask, d, disc = zip(*batch.items, strict=True)
            t = torch.from_numpy(np.stack([x["tiles"] for x in o]))
            s = torch.from_numpy(np.stack([x["scalars"] for x in o]))
            nt = torch.from_numpy(np.stack([x["tiles"] for x in no]))
            ns = torch.from_numpy(np.stack([x["scalars"] for x in no]))
            nm = torch.from_numpy(np.stack(nmask))
            a_t = torch.tensor(a)
            q = online(t, s).gather(1, a_t[:, None]).squeeze(1)
            with torch.no_grad():
                # double DQN: online picks the next action among legal ones, target values it
                na = online(nt, ns).masked_fill(~nm, float("-inf")).argmax(1)
                nq = target(nt, ns).gather(1, na[:, None]).squeeze(1)
                nq = torch.where(nm.any(1), nq, torch.zeros_like(nq))
                y = torch.tensor(ret, dtype=torch.float32) + \
                    torch.tensor(disc, dtype=torch.float32) * (1 - torch.tensor(d)) * nq
            td = y - q
            loss = (torch.from_numpy(batch.weights) * torch.nn.functional.smooth_l1_loss(
                q, y, reduction="none")).mean()
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(online.parameters(), 10.0)
            opt.step()
            buf.update_priorities(batch.indices, td.detach().numpy())
            if c.noisy:
                online.reset_noise()
            losses.append(float(loss))
        if step % c.target_every == 0:
            target.load_state_dict(online.state_dict())
        if step % c.eval_every == 0 or step == c.steps:
            snap = DuelingDQN(**model_config)
            snap.load_state_dict(online.state_dict())
            res = evaluate(lambda sd, m=snap: PolicyAgent(m, "dqn", 0.0, sd), "rule",
                           c.eval_hands)
            last_eval = res.as_dict()
            save_checkpoint(out, online, "dqn", model_config, step=step, **last_eval)
            logger.log(step, loss=float(np.mean(losses[-500:])) if losses else 0.0,
                       epsilon=epsilon(step, c), episodes=float(episodes),
                       sps=step / (time.time() - t0), **last_eval)
    logger.close()
    return last_eval


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("checkpoints/dqn_latest.pt"))
    ap.add_argument("--steps", type=int, default=200_000)
    ap.add_argument("--noisy", action="store_true")
    ap.add_argument("--eval-every", type=int, default=20_000)
    ap.add_argument("--run", default=f"dqn-{int(time.time())}")
    args = ap.parse_args()
    c = DQNConfig(steps=args.steps, noisy=args.noisy, eval_every=args.eval_every)
    print(train_dqn(c, args.out, args.run))


if __name__ == "__main__":
    main()
