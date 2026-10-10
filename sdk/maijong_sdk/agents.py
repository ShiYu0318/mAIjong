"""Reference agents: uniformly random and a greedy shanten minimiser."""

from __future__ import annotations

import random

from engine.shanten import discard_table, shanten
from maijong_sdk.base_agent import BaseAgent
from maijong_sdk.types import Action, ActionType, Observation

_CHI = {ActionType.CHI_LOW: (-2, -1), ActionType.CHI_MID: (-1, 1), ActionType.CHI_HIGH: (1, 2)}


def _counts(tiles: tuple[int, ...]) -> list[int]:
    c = [0] * 34
    for t in tiles:
        c[t] += 1
    return c


class RandomAgent(BaseAgent):
    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)

    def decide(self, obs: Observation, legal_actions: list[Action]) -> Action:
        return self.rng.choice(legal_actions)


class GreedyAgent(BaseAgent):
    """Wins when possible, discards to minimise shanten / maximise effective tiles,
    calls only when it lowers shanten, and declares ready whenever it can."""

    def decide(self, obs: Observation, legal_actions: list[Action]) -> Action:
        types = {a.type for a in legal_actions}
        if ActionType.HU in types:
            return Action(ActionType.HU)
        counts = _counts(obs.hand)
        n_melds = len(obs.melds[obs.seat])
        if obs.phase == "DISCARD":
            table = discard_table(counts, n_melds)
            options = [a for a in legal_actions if a.type in (ActionType.DISCARD, ActionType.TING)]
            if not options:
                return legal_actions[0]
            def key(a: Action) -> tuple[int, int, bool]:
                sh, uke = table[a.tile if a.tile is not None else 0]
                return sh, -len(uke), a.type is not ActionType.TING

            return min(options, key=key)
        base = shanten(counts, n_melds)
        assert obs.last_discard is not None
        t = obs.last_discard[1]
        for a in legal_actions:
            c = list(counts)
            if a.type is ActionType.PON:
                c[t] -= 2
            elif a.type in _CHI:
                o1, o2 = _CHI[a.type]
                c[t + o1] -= 1
                c[t + o2] -= 1
            else:
                continue
            after = min(sh for sh, _ in discard_table(c, n_melds + 1).values())
            if after < base:
                return a
        return Action(ActionType.PASS)
