"""Efficiency agent: the rule agent, but its discard looks ahead through its own draws.

The rule agent ranks discards by shanten and the count of tiles that improve the hand
right away (one draw ahead). This agent takes its top few discards and, for each, plays
out many random sequences of its own future draws from the unseen tiles (ignoring the
opponents), improving the hand greedily, and keeps the discard most likely to win before
the wall runs out. Every candidate sees the same draw sequences, so the comparison is
far less noisy than a full-game rollout. Defence (folding) and claims stay with the rule
agent.
"""

from __future__ import annotations

import random

from ai.agents.rule_agent import RuleAgent, RuleParams, _visible_counts
from engine import tiles
from engine.actions import Action, ActionType
from engine.game import GameState, Phase
from engine.shanten import shanten


def _greedy_discard(c: list[int], n_melds: int) -> None:
    """Drop the tile whose removal leaves the lowest shanten; among those, the most
    isolated one (fewest same-suit neighbours within two)."""
    best: tuple[int, int, int] | None = None
    for t in range(34):
        if not c[t]:
            continue
        c[t] -= 1
        sh = shanten(c, n_melds)
        c[t] += 1
        if t >= 27:
            near = c[t] - 1
        else:
            lo, hi = t - t % 9, t - t % 9 + 8
            near = sum(c[u] for u in range(max(lo, t - 2), min(hi, t + 2) + 1)) - 1
        key = (sh, near, t)
        if best is None or key < best:
            best = key
    assert best is not None
    c[best[2]] -= 1


def win_probability(counts: list[int], n_melds: int, draws: list[list[int]]) -> float:
    """Share of `draws` sequences in which the (3n+1) hand completes."""
    wins = 0
    for seq in draws:
        c = list(counts)
        for t in seq:
            c[t] += 1
            if shanten(c, n_melds) == -1:
                wins += 1
                break
            _greedy_discard(c, n_melds)
    return wins / max(1, len(draws))


class EfficiencyAgent(RuleAgent):
    name = "efficiency"

    def __init__(self, temperature: float = 0.0, seed: int | None = None, *,
                 samples: int = 48, top_k: int = 4, params: RuleParams | None = None,
                 **overrides: object) -> None:
        super().__init__(temperature, seed, params=params, **overrides)
        self.samples = samples
        self.top_k = top_k
        self.sim_rng = random.Random(seed)

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        if state.phase is not Phase.DISCARD or state.turn != seat or len(legal) == 1:
            return super().act(state, seat, legal)
        scored = self.scores(state, seat, legal)
        if any(a.type is ActionType.HU for a in legal) or getattr(self, "last_fold", 0.0):
            return super().act(state, seat, legal)
        # one action per tile: the rule agent's preferred form (plain discard or declare)
        by_tile: dict[int, Action] = {}
        for a in sorted(legal, key=lambda x: -scored[x]):
            if a.type in (ActionType.DISCARD, ActionType.TING) and a.tile is not None:
                by_tile.setdefault(a.tile, a)
        ranked = list(by_tile.values())[: self.top_k]
        best_other = max((scored[a] for a in legal if a.tile is None or
                          a.type not in (ActionType.DISCARD, ActionType.TING)), default=None)
        if len(ranked) < 2 or (best_other is not None and best_other >= scored[ranked[0]]):
            return super().act(state, seat, legal)  # a kong (or one option) wins outright
        seen = _visible_counts(state, seat)
        pool = [t for t in range(34) for _ in range(max(0, 4 - seen[t]))]
        n_draws = max(1, -(-state.drawable() // 4))
        draws = [self.sim_rng.sample(pool, min(n_draws, len(pool))) for _ in range(self.samples)]
        counts = tiles.to_counts(state.hands[seat])
        n_melds = len(state.melds[seat])
        best, best_p = ranked[0], -1.0
        for a in ranked:
            assert a.tile is not None
            c = list(counts)
            c[a.tile] -= 1
            p = win_probability(c, n_melds, draws)
            if p > best_p + 1e-9:  # ties keep the rule agent's order
                best, best_p = a, p
        return best


__all__ = ["EfficiencyAgent", "win_probability"]
