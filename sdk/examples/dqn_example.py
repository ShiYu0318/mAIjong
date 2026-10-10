"""Train a small DQN with the SDK environment (pip install maijong-sdk[rl] torch).

python dqn_example.py --episodes 2000 --output my_model.pt --seed 42
Then submit with:  maijong submit --agent dqn_agent.py:DQNAgent --model my_model.pt --name "MyDQN"
"""

from __future__ import annotations

import argparse
import random

import numpy as np
import torch
from maijong_sdk.env import MahjongEnv
from torch import nn


class QNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Flatten(), nn.Linear(34 * 14 + 13, 256), nn.ReLU(),
                                 nn.Linear(256, 256), nn.ReLU(), nn.Linear(256, 108))

    def forward(self, tiles: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([tiles.flatten(1), scalars], dim=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=2000)
    ap.add_argument("--output", default="my_model.pt")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    env = MahjongEnv(seed=args.seed)
    q, target = QNet(), QNet()
    target.load_state_dict(q.state_dict())
    opt = torch.optim.Adam(q.parameters(), lr=1e-3)
    memory: list[tuple] = []
    steps = 0
    for ep in range(args.episodes):
        obs, info = env.reset()
        done = False
        while not done:
            eps = max(0.05, 1 - steps / 20_000)
            legal = np.flatnonzero(info["legal_mask"])
            if random.random() < eps:
                a = int(random.choice(legal))
            else:
                with torch.no_grad():
                    t = torch.from_numpy(obs["tiles"])[None]
                    qs = q(t, torch.from_numpy(obs["scalars"])[None])[0]
                qs[~torch.from_numpy(info["legal_mask"])] = -1e9
                a = int(qs.argmax())
            nobs, r, done, _, ninfo = env.step(a)
            memory.append((obs, a, r, nobs, ninfo["legal_mask"], done))
            memory = memory[-50_000:]
            obs, info = nobs, ninfo
            steps += 1
            if len(memory) >= 512 and steps % 4 == 0:
                batch = random.sample(memory, 128)
                t = torch.from_numpy(np.stack([b[0]["tiles"] for b in batch]))
                s = torch.from_numpy(np.stack([b[0]["scalars"] for b in batch]))
                nt = torch.from_numpy(np.stack([b[3]["tiles"] for b in batch]))
                ns = torch.from_numpy(np.stack([b[3]["scalars"] for b in batch]))
                nm = torch.from_numpy(np.stack([b[4] for b in batch]))
                a_t = torch.tensor([b[1] for b in batch])
                r_t = torch.tensor([b[2] for b in batch], dtype=torch.float32)
                d_t = torch.tensor([b[5] for b in batch], dtype=torch.float32)
                with torch.no_grad():
                    nq = target(nt, ns).masked_fill(~nm, -1e9).max(1).values
                    nq = torch.where(nm.any(1), nq, torch.zeros_like(nq))
                    y = r_t + 0.99 * (1 - d_t) * nq
                pred = q(t, s).gather(1, a_t[:, None]).squeeze(1)
                loss = nn.functional.smooth_l1_loss(pred, y)
                opt.zero_grad()
                loss.backward()
                opt.step()
            if steps % 1000 == 0:
                target.load_state_dict(q.state_dict())
        if (ep + 1) % 100 == 0:
            print(f"episode {ep + 1}, steps {steps}")
    torch.save(q.state_dict(), args.output)
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
