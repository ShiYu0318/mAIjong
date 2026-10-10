"""Rule-based agent: minimise shanten, maximise effective tiles, avoid dangerous tiles.

Each candidate action gets a score; the action is sampled from softmax(score / T),
so the temperature controls difficulty (SPEC 04.4). When an opponent has declared a
ready hand (or the wall is nearly exhausted) the agent weighs deal-in danger more the
further it is from tenpai, folding with far-off hands.
"""

from __future__ import annotations

import math
import random

from ai.danger import tile_danger
from engine import tiles
from engine.actions import Action, ActionType
from engine.game import GameState, Phase
from engine.shanten import discard_table, shanten

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
            table = discard_table(counts, n_melds)
            current = min(sh for sh, _ in table.values())
            # defence weight: 0 while pushing, large when far from tenpai under threat
            fold = 0.0
            if any(state.declared_ting[p] for p in range(4) if p != seat):
                fold = {0: 4.0, 1: 12.0}.get(current, 40.0)
            elif state.drawable() < 24:
                fold = 2.0 if current <= 1 else 6.0
            for a in legal:
                score = self._turn_score(a, counts, n_melds, seen, table)
                if fold and a.type in (ActionType.DISCARD, ActionType.TING) and a.tile is not None:
                    score -= fold * tile_danger(state, seat, a.tile, seen)
                out[a] = score
        else:
            base = shanten(counts, n_melds)
            for a in legal:
                out[a] = self._response_score(a, counts, n_melds, base, state)
        return out

    def _turn_score(
        self, a: Action, counts: list[int], n_melds: int, seen: list[int],
        table: dict[int, tuple[int, list[int]]],
    ) -> float:
        if a.type is ActionType.HU:
            return 1000.0
        if a.type is ActionType.KONG:
            assert a.tile is not None
            c = list(counts)
            concealed = c[a.tile] == 4
            c[a.tile] -= 4 if concealed else 1  # added kong upgrades an existing pon
            sh = shanten(c, n_melds + 1 if concealed else n_melds)
            before = min(s for s, _ in table.values())
            return 50.0 if sh <= before else -50.0
        assert a.tile is not None
        sh, uke = table[a.tile]
        live = sum(4 - seen[t] for t in uke)
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
