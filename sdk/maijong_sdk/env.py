"""Gymnasium environment for SDK users (pip install maijong-sdk[rl]).

Opponents are BaseAgents (default: GreedyAgent). Observations use the same encoder as
the platform, so models trained here transfer directly.
"""

from __future__ import annotations

import random
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from engine.actions import ActionType, decode_action
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game
from maijong_sdk.agents import GreedyAgent
from maijong_sdk.base_agent import BaseAgent
from maijong_sdk.features import N_ACTIONS, N_SCALARS, encode, legal_mask
from maijong_sdk.types import observe


class MahjongEnv(gym.Env[dict[str, np.ndarray], int]):
    """Reward: +tai when the learning seat wins, −tai paid when it deals in, 0 otherwise."""

    def __init__(self, opponents: list[BaseAgent] | None = None, rotate_seat: bool = True,
                 seed: int | None = None) -> None:
        super().__init__()
        self.opponents = opponents or [GreedyAgent() for _ in range(3)]
        self.rotate_seat = rotate_seat
        self.seat = 0
        self._seed = seed
        self.observation_space = spaces.Dict({  # type: ignore[assignment]
            "tiles": spaces.Box(0, 4, (34, 14), np.float32),
            "scalars": spaces.Box(-100.0, 100.0, (N_SCALARS,), np.float32),
        })
        self.action_space = spaces.Discrete(N_ACTIONS)  # type: ignore[assignment]
        self.game: Any = None

    def _advance(self) -> None:
        g = self.game
        while g.phase is not Phase.ENDED:
            acting = acting_players(g)
            if self.seat in acting:
                break
            p = acting[0]
            opp = self.opponents[(p - self.seat - 1) % 4]
            g, _ = apply_action(g, p, opp.decide(observe(g, p), get_legal_actions(g, p)))
        self.game = g

    def _obs(self) -> dict[str, np.ndarray]:
        t, s = encode(observe(self.game, self.seat))
        return {"tiles": t, "scalars": s}

    def _info(self) -> dict[str, Any]:
        done = self.game.phase is Phase.ENDED
        mask = np.zeros(N_ACTIONS, bool) if done else legal_mask(
            get_legal_actions(self.game, self.seat))
        info: dict[str, Any] = {"legal_mask": mask, "seat": self.seat}
        if done:
            info["result"] = self.game.result
        return info

    def action_masks(self) -> np.ndarray:
        """For sb3-contrib MaskablePPO."""
        return np.asarray(self._info()["legal_mask"])

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None
              ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        super().reset(seed=seed if seed is not None else self._seed)
        self._seed = None
        for opp in self.opponents:
            rng = getattr(opp, "rng", None)
            if isinstance(rng, random.Random):
                rng.seed(int(self.np_random.integers(2**31)))
        while True:
            if self.rotate_seat:
                self.seat = int(self.np_random.integers(4))
            self.game = new_game(int(self.np_random.integers(2**62)))
            self._advance()
            if self.game.phase is not Phase.ENDED:
                return self._obs(), self._info()

    def step(self, action: int) -> tuple[dict[str, np.ndarray], float, bool, bool,
                                         dict[str, Any]]:
        legal = get_legal_actions(self.game, self.seat)
        a = decode_action(int(action))
        penalty = 0.0
        if a not in legal:
            a = next((x for x in legal if x.type is ActionType.PASS), legal[0])
            penalty = -0.1
        self.game, _ = apply_action(self.game, self.seat, a)
        self._advance()
        done = self.game.phase is Phase.ENDED
        reward = penalty
        if done and self.game.result["kind"] == "HU":
            r = self.game.result
            by_payer = {int(k): v for k, v in r.get("tai_by_payer", {}).items()}
            if r["winner"] == self.seat:
                reward += max(by_payer.values(), default=0)
            elif self.seat in by_payer and not r.get("self_draw"):
                reward -= by_payer[self.seat]
        return self._obs(), float(reward), done, False, self._info()
