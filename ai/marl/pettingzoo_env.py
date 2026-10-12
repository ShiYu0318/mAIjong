"""PettingZoo AEC environment: all four seats are agents (SPEC 05.1, multi-agent view).

Follows the PettingZoo "classic" convention used by chess / connect four:
observation = {"observation": {"tiles", "scalars"}, "action_mask": int8 (108,)}.
Only seats that may act are selected; during a call window every seat with a call
option acts in turn. Rewards arrive when the hand ends: payments / `score_scale`.

    from ai.marl import env
    e = env()
    e.reset(seed=0)
    for agent in e.agent_iter():
        obs, reward, term, trunc, info = e.last()
        action = None if term or trunc else int(np.flatnonzero(obs["action_mask"])[0])
        e.step(action)

Works with any library that speaks PettingZoo (RLlib, Tianshou, CleanRL, AgileRL…).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from gymnasium import spaces
from pettingzoo import AECEnv
from pettingzoo.utils import wrappers

from ai.features import N_SCALARS, encode, mask_for
from engine.actions import N_ACTIONS, decode_action
from engine.game import GameState, Phase, acting_players, apply_action, new_game

AGENTS = [f"player_{i}" for i in range(4)]


class MahjongAECEnv(AECEnv[str, dict[str, Any], int | None]):
    metadata = {"render_modes": ["ansi"], "name": "maijong_tw16_v0", "is_parallelizable": False}

    def __init__(self, score_scale: float = 100.0, render_mode: str | None = None) -> None:
        super().__init__()
        self.score_scale = score_scale
        self.render_mode = render_mode
        self.possible_agents = list(AGENTS)
        obs_space = spaces.Dict({
            "observation": spaces.Dict({
                "tiles": spaces.Box(0, 4, (34, 14), np.float32),
                "scalars": spaces.Box(-100.0, 100.0, (N_SCALARS,), np.float32),
            }),
            "action_mask": spaces.Box(0, 1, (N_ACTIONS,), np.int8),
        })
        self.observation_spaces = {a: obs_space for a in AGENTS}
        self.action_spaces = {a: spaces.Discrete(N_ACTIONS) for a in AGENTS}
        self.game: GameState | None = None
        self._rng = np.random.default_rng()

    def observation_space(self, agent: str) -> spaces.Space[Any]:
        return self.observation_spaces[agent]

    def action_space(self, agent: str) -> spaces.Space[Any]:
        return self.action_spaces[agent]

    def observe(self, agent: str) -> dict[str, Any]:
        g = self.game
        assert g is not None
        seat = AGENTS.index(agent)
        t, s = encode(g, seat)
        live = g.phase is not Phase.ENDED and seat in acting_players(g)
        mask = mask_for(g, seat).astype(np.int8) if live else np.zeros(N_ACTIONS, np.int8)
        return {"observation": {"tiles": t, "scalars": s}, "action_mask": mask}

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> None:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self.agents = list(self.possible_agents)
        self.rewards = {a: 0.0 for a in self.agents}
        self._cumulative_rewards = {a: 0.0 for a in self.agents}
        self.terminations = {a: False for a in self.agents}
        self.truncations = {a: False for a in self.agents}
        self.infos: dict[str, dict[str, Any]] = {a: {} for a in self.agents}
        while True:  # skip the rare hand that ends before anyone decides
            self.game = new_game(int(self._rng.integers(2**62)))
            if self.game.phase is not Phase.ENDED:
                break
        self.agent_selection = AGENTS[acting_players(self.game)[0]]

    def step(self, action: int | None) -> None:
        agent = self.agent_selection
        if self.terminations[agent] or self.truncations[agent]:
            self._was_dead_step(action)
            return
        g = self.game
        assert g is not None and action is not None
        seat = AGENTS.index(agent)
        self._cumulative_rewards[agent] = 0.0
        if not mask_for(g, seat)[int(action)]:
            raise ValueError(f"illegal action {action} for {agent}")
        self.game, _ = apply_action(g, seat, decode_action(int(action)))
        self._clear_rewards()
        if self.game.phase is Phase.ENDED:
            result = self.game.result or {}
            payments = result.get("payments", [0, 0, 0, 0])
            for i, a in enumerate(AGENTS):
                self.rewards[a] = float(payments[i]) / self.score_scale
                self.terminations[a] = True
                self.infos[a] = {"result": result}
            self.agent_selection = AGENTS[(seat + 1) % 4]
        else:
            self.agent_selection = AGENTS[acting_players(self.game)[0]]
        self._accumulate_rewards()

    def render(self) -> str | None:
        if self.game is None:
            return None
        from engine import tiles

        g = self.game
        return " | ".join(f"{a}: {tiles.names(g.hands[i])}" for i, a in enumerate(AGENTS))

    def close(self) -> None:
        pass


def raw_env(**kwargs: Any) -> MahjongAECEnv:
    return MahjongAECEnv(**kwargs)


def env(**kwargs: Any) -> AECEnv[str, dict[str, Any], int | None]:
    """Wrapped environment with PettingZoo's order-enforcing checks."""
    e: AECEnv[str, dict[str, Any], int | None] = raw_env(**kwargs)
    e = wrappers.OrderEnforcingWrapper(e)
    return e
