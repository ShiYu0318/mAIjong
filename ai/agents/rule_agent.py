"""Rule-based agent: minimise shanten, maximise effective tiles, avoid dangerous tiles.

Each candidate action gets a score; the action is sampled from softmax(score / T),
so the temperature controls difficulty (SPEC 04.4). When an opponent has declared a
ready hand (or the wall is nearly exhausted) the agent weighs deal-in danger more the
further it is from tenpai, folding with far-off hands.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from ai.danger import suspected_danger, suspected_threats, tile_danger
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


@dataclass(frozen=True)
class RuleParams:
    """Every number the rule agent decides with; the defaults are the original agent.
    `ai.training.tune` searches these against a mixed pool of opponents."""

    w_shanten: float = 10.0  # per step of shanten after the discard
    w_live: float = 0.1  # per unseen copy of the tiles that would improve the hand
    honor_discard: float = 0.05  # small push to let go of isolated honours early
    ting_bonus: float = 0.5  # declaring ready (+1 tai)
    declare: str | int = "always"  # "always" | "never" | N = only with >= N unseen waits
    calls: str = "shanten"  # "shanten" | "keep" | "near" | "ready" | "never"
    value_pon: float = 0.0  # bonus for ponning a dragon or our seat/round wind (1 tai)
    flush: int = 0  # chase a one-suit hand once this many tiles fit it; 0 = off
    flush_far: float = 4.0  # discard bonus for a stray tile while many remain
    flush_near: float = 12.0  # ... once at most three stray tiles remain
    fold_ready: float = 4.0  # danger weight under a declared threat, hand ready
    fold_one: float = 12.0  # ... one away
    fold_far: float = 40.0  # ... further
    late_wall: int = 24  # drawable tiles left when the late-game caution starts
    fold_late_near: float = 2.0
    fold_late_far: float = 6.0
    # undeclared opponents that look ready (humans often stay silent); 0 turns a sign off
    threat_melds: int = 0  # this many melds marks an opponent as a threat
    threat_turn: int = 0  # ... or this many discards
    threat_scale: float = 0.5  # fold weight against such a threat, relative to a declared one


class RuleAgent:
    name = "rule"

    def __init__(self, temperature: float = 0.0, seed: int | None = None, *,
                 params: RuleParams | None = None, **overrides: object) -> None:
        """`overrides` set single RuleParams fields (declare=4, calls="near", flush=13…)."""
        self.temperature = temperature
        self.rng = random.Random(seed)
        self.params = replace(params or RuleParams(), **overrides)  # type: ignore[arg-type]

    # -------------------------------------------------------------- scoring
    def scores(self, state: GameState, seat: int, legal: list[Action]) -> dict[Action, float]:
        P = self.params
        counts = tiles.to_counts(state.hands[seat])
        n_melds = len(state.melds[seat])
        seen = _visible_counts(state, seat)
        out: dict[Action, float] = {}
        if state.phase is Phase.DISCARD:
            table = discard_table(counts, n_melds)
            current = min(sh for sh, _ in table.values())
            # defence weight: 0 while pushing, large when far from tenpai under threat
            fold = 0.0
            suspects: list[int] = []
            if any(state.declared_ting[p] for p in range(4) if p != seat):
                fold = {0: P.fold_ready, 1: P.fold_one}.get(current, P.fold_far)
            else:
                suspects = suspected_threats(state, seat, P.threat_melds, P.threat_turn)
                if suspects:
                    fold = P.threat_scale * {0: P.fold_ready, 1: P.fold_one}.get(
                        current, P.fold_far)
                elif state.drawable() < P.late_wall:
                    fold = P.fold_late_near if current <= 1 else P.fold_late_far
            flush_suit = self._flush_suit(state, seat, counts)
            self.last_fold = fold  # read by agents that build on this one
            for a in legal:
                score = self._turn_score(a, counts, n_melds, seen, table)
                if flush_suit is not None and a.tile is not None and \
                        a.type in (ActionType.DISCARD, ActionType.TING):
                    score += self._flush_bonus(a.tile, flush_suit, counts)
                if fold and a.type in (ActionType.DISCARD, ActionType.TING) and a.tile is not None:
                    danger = suspected_danger(state, a.tile, seen, suspects) if suspects \
                        else tile_danger(state, seat, a.tile, seen)
                    score -= fold * danger
                out[a] = score
        else:
            base = shanten(counts, n_melds)
            for a in legal:
                out[a] = self._response_score(a, counts, n_melds, base, state, seat)
        return out

    def _flush_suit(self, state: GameState, seat: int, counts: list[int]) -> int | None:
        """The suit to chase when enough of the hand (and every meld) already fits it."""
        if not self.params.flush:
            return None
        meld_suits = {tiles.suit_of(t) for m in state.melds[seat] for t in m.tiles
                      if t is not None and not tiles.is_honor(t)}
        if len(meld_suits) > 1:
            return None
        honors = sum(counts[t] for t in range(27, 34))
        best, best_n = None, -1
        for suit in range(3):
            if meld_suits and suit not in meld_suits:
                continue
            n = sum(counts[suit * 9:(suit + 1) * 9]) + honors
            if n > best_n:
                best, best_n = suit, n
        return best if best_n >= self.params.flush else None

    def _flush_bonus(self, tile: int, suit: int, counts: list[int]) -> float:
        if tiles.is_honor(tile) or tiles.suit_of(tile) == suit:
            return 0.0
        off = sum(counts[t] for t in range(27) if tiles.suit_of(t) != suit)
        # few stray tiles left: worth a step of shanten to clear them; many: a tie-breaker
        return self.params.flush_near if off <= 3 else self.params.flush_far

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
        P = self.params
        sh, uke = table[a.tile]
        live = sum(4 - seen[t] for t in uke)
        score = -P.w_shanten * sh + P.w_live * live
        # mild preference for discarding isolated honours / terminals early
        if tiles.is_honor(a.tile):
            score += P.honor_discard
        if a.type is ActionType.TING:
            if P.declare == "always":
                score += P.ting_bonus  # +1 tai, but the hand is locked and opponents fold
            elif P.declare == "never" or live < int(P.declare):
                score -= P.ting_bonus  # the plain discard of the same tile wins the tie
            else:
                score += P.ting_bonus
        return score

    def _response_score(
        self, a: Action, counts: list[int], n_melds: int, base: int, state: GameState,
        seat: int,
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
        P = self.params
        value_tiles = {31, 32, 33, 27 + state.seat_wind(seat), 27 + state.round_wind}
        if P.value_pon and a.type is ActionType.PON and t in value_tiles and after <= base:
            return 2.0 + P.value_pon  # a value pon is worth a tai even without progress
        if P.calls == "never":
            return -1.0
        if P.calls == "ready":
            return 2.0 if after <= 0 < base else -1.0
        if P.calls == "near":
            return 2.0 if after < base and after <= 1 else -1.0
        if P.calls == "keep":  # also when the call keeps shanten (more chances to win fast)
            return 2.0 if after < base else (0.5 if after == base else -1.0)
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
