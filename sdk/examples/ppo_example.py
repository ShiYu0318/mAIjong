"""Train with sb3-contrib MaskablePPO (pip install maijong-sdk[rl] sb3-contrib).

python ppo_example.py --steps 200000 --output ppo_model.zip
"""

from __future__ import annotations

import argparse

import gymnasium as gym
import numpy as np
from maijong_sdk.env import MahjongEnv


class Flatten(gym.ObservationWrapper):
    """MaskablePPO's default policy wants a flat Box observation."""

    def __init__(self, env: MahjongEnv) -> None:
        super().__init__(env)
        self.observation_space = gym.spaces.Box(-100, 100, (34 * 14 + 13,), np.float32)

    def observation(self, obs):
        return np.concatenate([obs["tiles"].ravel(), obs["scalars"]]).astype(np.float32)

    def action_masks(self) -> np.ndarray:
        return self.env.action_masks()


def main() -> None:
    from sb3_contrib import MaskablePPO

    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=200_000)
    ap.add_argument("--output", default="ppo_model.zip")
    args = ap.parse_args()
    model = MaskablePPO("MlpPolicy", Flatten(MahjongEnv(seed=0)), verbose=1)
    model.learn(total_timesteps=args.steps)
    model.save(args.output)


if __name__ == "__main__":
    main()
