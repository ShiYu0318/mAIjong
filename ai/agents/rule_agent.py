"""Rule-based agent: minimise shanten, maximise effective tiles.

Each candidate action gets a score; the action is sampled from softmax(score / T),
so the temperature controls difficulty (SPEC 04.4).
"""

from __future__ import annotations

import math
import random

from engine import tiles
from engine.actions import Action, ActionType
from engine.game import GameState, Phase
from engine.shanten import shanten, uke_ire

_CHI_OFFSETS = {
    ActionType.CHI_LOW: (-2, -1),
    ActionType.CHI_MID: (-1, 1),
    ActionType.CHI_HIGH: (1, 2),
}


def _visible_counts(state: GameState, seat: int) -> list[int]:
    """Copies of each tile the seat can see (own hand, all melds and discards)."""
    seen = tiles.to_counts(state.hands[seat])
    for p in range(4):
        for t in state.discards[p]:
            seen[t] += 1
        for m in state.melds[p]:
            for t in m.tiles:
                seen[t] += 1
    return seen


def _live_ukeire(counts: list[int], n_melds: int, seen: list[int]) -> int:
    return sum(4 - seen[t] for t in uke_ire(counts, n_melds))


def _best_discard_shanten(counts: list[int], n_melds: int) -> int:
    best = 99
    for t in range(34):
        if counts[t]:
            counts[t] -= 1
            best = min(best, shanten(counts, n_melds))
            counts[t] += 1
    return best


class RuleAgent:
    name = "rule"

    def __init__(self, temperature: float = 0.0, seed: int | None = None) -> None:
        self.temperature = temperature
        self.rng = random.Random(seed)

    # -------------------------------------------------------------- scoring
    def scores(self, state: GameState, seat: int, legal: list[Action]) -> dict[Action, float]:
        counts = tiles.to_counts(state.hands[seat])
        n_melds = len(state.melds[seat])
        seen = _visible_counts(state, seat)
        out: dict[Action, float] = {}
        if state.phase is Phase.DISCARD:
            for a in legal:
                out[a] = self._turn_score(a, counts, n_melds, seen, state, seat)
        else:
            base = shanten(counts, n_melds)
            for a in legal:
                out[a] = self._response_score(a, counts, n_melds, base, state)
        return out

    def _turn_score(
        self, a: Action, counts: list[int], n_melds: int, seen: list[int],
        state: GameState, seat: int,
    ) -> float:
        if a.type is ActionType.HU:
            return 1000.0
        if a.type is ActionType.KONG:
            assert a.tile is not None
            c = list(counts)
            concealed = c[a.tile] == 4
            c[a.tile] -= 4 if concealed else 1  # added kong upgrades an existing pon
            sh = shanten(c, n_melds + 1 if concealed else n_melds)
            before = _best_discard_shanten(list(counts), n_melds)
            return 50.0 if sh <= before else -50.0
        assert a.tile is not None
        counts[a.tile] -= 1
        sh = shanten(counts, n_melds)
        live = _live_ukeire(counts, n_melds, seen)
        counts[a.tile] += 1
        score = -10.0 * sh + 0.1 * live
        # mild preference for discarding isolated honours / terminals early
        if tiles.is_honor(a.tile):
            score += 0.05
        if a.type is ActionType.TING:
            score += 0.5  # declaring ready earns 1 tai and costs nothing for a bot
        return score

    def _response_score(
        self, a: Action, counts: list[int], n_melds: int, base: int, state: GameState
    ) -> float:
        if a.type is ActionType.HU:
            return 1000.0
        if a.type is ActionType.PASS:
            return 0.0
        assert state.last_discard is not None
        _, t = state.last_discard
        c = list(counts)
        if a.type is ActionType.PON:
            c[t] -= 2
        elif a.type is ActionType.KONG:
            c[t] -= 3
            return 1.0 if shanten(c, n_melds + 1) <= base else -1.0
        else:
            o1, o2 = _CHI_OFFSETS[a.type]
            c[t + o1] -= 1
            c[t + o2] -= 1
        after = _best_discard_shanten(c, n_melds + 1)
        return 2.0 if after < base else -1.0

    # -------------------------------------------------------------- policy
    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        scored = self.scores(state, seat, legal)
        if self.temperature < 0.01:
            best = max(scored.values())
            top = [a for a, v in scored.items() if v == best]
            return self.rng.choice(top)
        mx = max(scored.values())
        weights = [math.exp((v - mx) / self.temperature) for v in scored.values()]
        return self.rng.choices(list(scored), weights=weights, k=1)[0]
