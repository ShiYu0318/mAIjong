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
from ai.danger import safe_against
from engine import tiles
from engine.actions import Action, ActionType
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions
from engine.hand import MeldType
from engine.ting import waiting_tiles


def _ready_hand(avail: list[int], size: int, n_melds: int, safe: set[int],
                rng: random.Random, tries: int = 100) -> list[int] | None:
    """A random concealed hand of `size` (3n+1) tiles that is ready, built from the
    `avail` counts: n sets and a pair minus one tile. Its waits must avoid `safe` (tiles the
    player let pass after declaring). None if no such hand turns up."""
    n_sets = (size - 1) // 3
    for _ in range(tries):
        c = list(avail)
        hand: list[int] = []
        pairs = [t for t in range(34) if c[t] >= 2]
        if not pairs:
            return None
        pr = rng.choice(pairs)
        c[pr] -= 2
        hand += [pr, pr]
        ok = True
        for _ in range(n_sets):
            for _ in range(20):
                if rng.random() < 0.75:
                    suit, r = rng.randrange(3), rng.randrange(7)
                    trio = [suit * 9 + r, suit * 9 + r + 1, suit * 9 + r + 2]
                    if all(c[t] for t in trio):
                        for t in trio:
                            c[t] -= 1
                        hand += trio
                        break
                else:
                    t = rng.randrange(34)
                    if c[t] >= 3:
                        c[t] -= 3
                        hand += [t, t, t]
                        break
            else:
                ok = False
                break
        if not ok:
            continue
        hand.remove(rng.choice(hand))
        waits = waiting_tiles(tiles.to_counts(hand), n_melds)
        if waits and not safe.intersection(waits):
            return sorted(hand)
    return None


def determinize(state: GameState, seat: int, rng: random.Random,
                ready: bool = False) -> GameState:
    """A copy of `state` where everything `seat` cannot see is redealt at random: the other
    players' concealed tiles and the wall, each keeping its size. With `ready`, a player
    who declared ready gets a ready hand consistent with what they let pass."""
    s = state.clone()
    others = [p for p in range(4) if p != seat]
    pool = [t for p in others for t in s.hands[p]] + list(s.wall)
    # flowers never sit in a hand (they are replaced on the spot), so hands come from the
    # unseen playable tiles and every flower goes back into the wall
    playable = [t for t in pool if t < tiles.N_PLAYABLE]
    flowers = [t for t in pool if t >= tiles.N_PLAYABLE]
    avail = tiles.to_counts(playable)
    fixed: dict[int, list[int]] = {}
    if ready:
        for p in others:
            if not s.declared_ting[p]:
                continue
            hand = _ready_hand(avail, len(s.hands[p]), len(s.melds[p]),
                               safe_against(state, p), rng)
            if hand is not None:
                fixed[p] = hand
                for t in hand:
                    avail[t] -= 1
    rest = [t for t in range(34) for _ in range(avail[t])]
    rng.shuffle(rest)
    k = 0
    for p in others:
        if p in fixed:
            s.hands[p] = fixed[p]
            continue
        n = len(s.hands[p])
        s.hands[p] = sorted(rest[k:k + n])
        k += n
    wall = rest[k:] + flowers
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
                 params: RuleParams | None = None, defense: bool = False) -> None:
        self.samples = samples
        self.top_k = top_k
        self.z = z  # how sure (paired t) the search must be before overriding the rule agent
        # defense: search only under a declared threat or late in the hand (short, low-noise
        # rollouts where push/fold matters most), with declared hands sampled as ready
        self.defense = defense
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
        if _hidden_kongs(state, seat):
            return False  # a concealed kong's tiles are not ours to see
        threat = any(state.declared_ting[p] for p in range(4) if p != seat)
        if self.defense:
            return threat or state.drawable() < self.rule.params.late_wall
        return not threat  # uniform hands are rarely ready: leave declared threats alone

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
            world = determinize(state, seat, self.rng, ready=self.defense)
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
