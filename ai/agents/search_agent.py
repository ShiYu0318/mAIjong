"""Search agent: perfect-information Monte Carlo (PIMC) over the rule agent.

On its own discard turn the agent samples worlds consistent with what its seat can see
(opponents' concealed tiles and the wall are reshuffled from the unseen pool), plays every
shortlisted action to the end of the hand in each world with rule agents, and keeps the
action with the best average result for its seat. All candidates share the same worlds
(common random numbers), so small differences are not drowned in deal-to-deal noise.

It searches only where it is cheap and sound:
- discard turns (claims stay with the rule agent: the server prepared each opponent's
  legal claims from their real hand, which a sampled world cannot reuse);
- while nobody has declared ready (uniformly sampled hands are almost never ready, so a
  search would underrate the danger; the rule agent's defence takes over then).
"""

from __future__ import annotations

import random
import time

from ai.agents.rule_agent import RuleAgent, RuleParams
from engine import tiles
from engine.actions import Action, ActionType
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions
from engine.hand import MeldType


def determinize(state: GameState, seat: int, rng: random.Random) -> GameState:
    """A copy of `state` where everything `seat` cannot see is redealt at random: the other
    players' concealed tiles and the wall, each keeping its size."""
    s = state.clone()
    others = [p for p in range(4) if p != seat]
    pool = [t for p in others for t in s.hands[p]] + list(s.wall)
    # flowers never sit in a hand (they are replaced on the spot), so hands come from the
    # unseen playable tiles and every flower goes back into the wall
    playable = [t for t in pool if t < tiles.N_PLAYABLE]
    flowers = [t for t in pool if t >= tiles.N_PLAYABLE]
    rng.shuffle(playable)
    k = 0
    for p in others:
        n = len(s.hands[p])
        s.hands[p] = sorted(playable[k:k + n])
        k += n
    wall = playable[k:] + flowers
    rng.shuffle(wall)
    s.wall = wall
    return s


def _hidden_kongs(state: GameState, seat: int) -> bool:
    return any(m.type is MeldType.AN_KONG for p in range(4) if p != seat for m in state.melds[p])


def _paired_t(diffs: list[float]) -> float:
    n = len(diffs)
    if n < 2:
        return 0.0
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    if var == 0:
        return float("inf") if mean > 0 else 0.0
    return mean / (var / n) ** 0.5


class SearchAgent:
    name = "search"

    def __init__(self, samples: int = 32, top_k: int = 3, seed: int | None = None,
                 time_budget: float | None = None, z: float = 2.0,
                 params: RuleParams | None = None) -> None:
        self.samples = samples
        self.top_k = top_k
        self.z = z  # how sure (paired t) the search must be before overriding the rule agent
        self.time_budget = time_budget  # seconds per decision; None = all samples
        self.rng = random.Random(seed)
        # `params` (e.g. tuned ones) drive both the default choice and the rollouts
        self.rule = RuleAgent(0.0, seed, params=params)
        self._rollout = [RuleAgent(0.0, (seed or 0) * 7 + i, params=params) for i in range(4)]
        self.stats = {"searched": 0, "deferred": 0}

    def _should_search(self, state: GameState, seat: int, legal: list[Action]) -> bool:
        if state.phase is not Phase.DISCARD or state.turn != seat:
            return False
        if any(a.type is ActionType.HU for a in legal):
            return False  # always take the win
        if any(state.declared_ting[p] for p in range(4) if p != seat):
            return False  # defence: see the module docstring
        return not _hidden_kongs(state, seat)  # a concealed kong's tiles are not ours to see

    def _rollout_value(self, s: GameState, seat: int) -> float:
        while s.phase is not Phase.ENDED:
            p = acting_players(s)[0]
            s, _ = apply_action(s, p, self._rollout[p].act(s, p, get_legal_actions(s, p)))
        assert s.result is not None
        return float(s.result["payments"][seat])

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        if len(legal) == 1 or not self._should_search(state, seat, legal):
            self.stats["deferred"] += 1
            return self.rule.act(state, seat, legal)
        scored = self.rule.scores(state, seat, legal)
        ranked = sorted(legal, key=lambda a: -scored[a])
        cands = ranked[: self.top_k]
        if len(cands) == 1:
            return cands[0]
        self.stats["searched"] += 1
        values: list[list[float]] = [[] for _ in cands]
        start = time.perf_counter()
        for _ in range(self.samples):
            world = determinize(state, seat, self.rng)
            for i, a in enumerate(cands):
                after, _ = apply_action(world, seat, a)
                values[i].append(self._rollout_value(after, seat))
            if self.time_budget is not None and time.perf_counter() - start > self.time_budget:
                break
        # Hand results are very noisy, so the best average of a few rollouts is mostly luck.
        # Keep the rule agent's choice unless another candidate beats it on the same worlds
        # by a paired t of at least `z`.
        best, best_t = 0, self.z
        for i in range(1, len(cands)):
            t = _paired_t([a - b for a, b in zip(values[i], values[0], strict=True)])
            if t >= best_t:
                best, best_t = i, t
        if best:
            self.stats["overrides"] = self.stats.get("overrides", 0) + 1
        return cands[best]


__all__ = ["SearchAgent", "determinize"]
