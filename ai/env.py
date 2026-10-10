"""Gymnasium environment (SPEC 05.1): one learning seat, three opponent agents.

Observation: {"tiles": (34, 14) float32, "scalars": (13,) float32}
Action: Discrete(108) as in engine/actions.py; info["legal_mask"] is a bool array (108,).
Shaped rewards compare hand quality (shanten, effective tiles) between consecutive
decisions of the learning seat; terminal rewards follow ai/reward.py.
"""

from __future__ import annotations

import random
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from ai.agents import Agent, RandomAgent
from ai.features import N_SCALARS, _effective_tiles, encode, mask_for
from ai.reward import DEFAULT_REWARD_CONFIG, GameResult, StepData, compute_shaped_reward
from engine import tiles
from engine.actions import N_ACTIONS, ActionType, decode_action
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions, new_game


class MahjongEnv(gym.Env[dict[str, np.ndarray], int]):
    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        seat: int = 0,
        opponent_agents: list[Agent] | None = None,
        reward_config: dict[str, float] | None = None,
        seed: int | None = None,
        rotate_seat: bool = False,
        render_mode: str | None = None,
    ) -> None:
        super().__init__()
        self.seat = seat
        self.rotate_seat = rotate_seat
        self.seed_value = seed
        self.opponent_agents = opponent_agents or [RandomAgent(i) for i in range(3)]
        self.reward_config = reward_config or DEFAULT_REWARD_CONFIG
        self.render_mode = render_mode
        self.observation_space = spaces.Dict({
            "tiles": spaces.Box(low=0, high=4, shape=(34, 14), dtype=np.float32),
            "scalars": spaces.Box(low=-100.0, high=100.0, shape=(N_SCALARS,), dtype=np.float32),
        })
        self.action_space = spaces.Discrete(N_ACTIONS)
        self.game: GameState | None = None
        self._quality: tuple[int, int] = (8, 0)
        self._flowers = 0

    # ------------------------------------------------------------------ helpers
    def _opponent(self, player: int) -> Agent:
        idx = (player - self.seat - 1) % 4
        return self.opponent_agents[idx]

    def _advance(self) -> None:
        """Let the other seats act until the learning seat must decide or the hand ends."""
        g = self.game
        assert g is not None
        while g.phase is not Phase.ENDED:
            acting = acting_players(g)
            if self.seat in acting:
                break
            p = acting[0]
            a = self._opponent(p).act(g, p, get_legal_actions(g, p))
            g, _ = apply_action(g, p, a)
        self.game = g

    def _reseed_opponents(self) -> None:
        """Make episodes reproducible from the reset seed (opponents keep their own RNGs)."""
        for agent in self.opponent_agents:
            seed = int(self.np_random.integers(2**31))
            rng = getattr(agent, "rng", None)
            if isinstance(rng, random.Random):
                rng.seed(seed)
            gen = getattr(agent, "gen", None)
            if gen is not None and hasattr(gen, "manual_seed"):
                gen.manual_seed(seed)

    def _measure(self) -> tuple[int, int]:
        g = self.game
        assert g is not None
        counts = tiles.to_counts(g.hands[self.seat])
        sh, uke = _effective_tiles(counts, len(g.melds[self.seat]))
        return sh, sum(4 - counts[t] for t in uke)

    def _own_flowers(self) -> int:
        g = self.game
        assert g is not None
        own = set(tiles.seat_flowers(g.seat_wind(self.seat)))
        return sum(1 for f in g.flowers[self.seat] if f in own)

    def _obs(self) -> dict[str, np.ndarray]:
        assert self.game is not None
        t, s = encode(self.game, self.seat)
        return {"tiles": t, "scalars": s}

    def _info(self) -> dict[str, Any]:
        g = self.game
        assert g is not None
        mask = mask_for(g, self.seat) if g.phase is not Phase.ENDED else np.zeros(N_ACTIONS, bool)
        info: dict[str, Any] = {"legal_mask": mask, "seat": self.seat}
        if g.result is not None:
            info["result"] = g.result
        return info

    # ------------------------------------------------------------------ gym API
    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        super().reset(seed=seed if seed is not None else self.seed_value)
        self.seed_value = None  # only the first reset uses the constructor seed
        self._reseed_opponents()
        while True:
            if self.rotate_seat:
                self.seat = int(self.np_random.integers(4))
            game_seed = int(self.np_random.integers(2**62))
            self.game = new_game(game_seed)
            self._advance()
            if self.game.phase is not Phase.ENDED:  # skip hands decided before we act
                break
        self._quality = self._measure()
        self._flowers = self._own_flowers()
        return self._obs(), self._info()

    def step(
        self, action: int
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        g = self.game
        assert g is not None and g.phase is not Phase.ENDED
        a = decode_action(int(action))
        legal = get_legal_actions(g, self.seat)
        illegal = a not in legal
        if illegal:
            # never crash on an unmasked sample: play PASS (or the first legal action) and
            # penalise; strict callers can check info["illegal_action"]
            a = next((x for x in legal if x.type is ActionType.PASS), legal[0])
        self.game, _ = apply_action(g, self.seat, a)
        self._advance()
        done = self.game.phase is Phase.ENDED
        before = self._quality
        after = self._measure() if not done else before
        flowers = self._own_flowers()
        step = StepData(self.seat, before[0], after[0], before[1], after[1],
                        own_flowers_gained=max(0, flowers - self._flowers), is_final=done)
        result = GameResult.from_result(self.game.result, self.seat) \
            if done and self.game.result else None
        reward = compute_shaped_reward(step, [], result, self.reward_config)
        if illegal:
            reward += self.reward_config.get("illegal_penalty", -0.1)
        self._quality, self._flowers = after, flowers
        info = self._info()
        info["illegal_action"] = illegal
        return self._obs(), float(reward), done, False, info

    def render(self) -> str | None:  # type: ignore[override]
        if self.game is None:
            return None
        g = self.game
        return (f"seat {self.seat} hand: {tiles.names(g.hands[self.seat])} | "
                f"phase {g.phase.value} drawable {g.drawable()}")
