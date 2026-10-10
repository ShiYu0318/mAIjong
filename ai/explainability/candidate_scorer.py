"""Score every legal discard for hints, coaching and replay overlays (SPEC 05.8)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ai.agents.rule_agent import RuleAgent
from ai.danger import tile_danger, visible_counts
from engine import tiles
from engine.actions import Action, ActionType
from engine.game import GameState, Phase, get_legal_actions
from engine.hand import Meld
from engine.score import WinContext, score_hand
from engine.shanten import discard_table


@dataclass
class CandidateScore:
    tile: int
    shanten_after: int
    uke_ire: list[int]
    uke_count: int  # live copies of the effective tiles
    danger: float
    agent_score: float
    can_declare: bool
    waits: list[int] = field(default_factory=list)
    best_tai: int | None = None  # best tai over the waits when tenpai

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["name"] = tiles.name(self.tile)
        return d


def best_tai_for_waits(concealed: list[int], melds: list[Meld], flowers: list[int],
                       seat_wind: int, round_wind: int, waits: list[int]) -> int | None:
    """Highest hand tai among the waiting tiles (won on a discard, dealer tai excluded)."""
    best: int | None = None
    for w in waits:
        ctx = WinContext(
            winner=0, dealer=1, dealer_streak=0, seat_wind=seat_wind, round_wind=round_wind,
            concealed=tuple(sorted([*concealed, w])), melds=tuple(melds),
            flowers=tuple(flowers), win_tile=w, loser=1, tile_from_other=True,
        )
        tai = score_hand(ctx).tai
        best = tai if best is None else max(best, tai)
    return best


def score_all_discards(state: GameState, seat: int, agent: RuleAgent | None = None
                       ) -> list[CandidateScore]:
    """Rank the seat's legal discards: lowest shanten first, then most live effective tiles."""
    if state.phase is not Phase.DISCARD or state.turn != seat:
        return []
    legal = get_legal_actions(state, seat)
    discards = sorted(
        {a.tile for a in legal if a.type is ActionType.DISCARD and a.tile is not None}
    )
    if not discards:
        return []
    declare_ok = {a.tile for a in legal if a.type is ActionType.TING}
    counts = tiles.to_counts(state.hands[seat])
    n_melds = len(state.melds[seat])
    table = discard_table(counts, n_melds)
    seen = visible_counts(state, seat)
    agent = agent or RuleAgent(0.0)
    agent_scores = agent.scores(state, seat, legal)
    out: list[CandidateScore] = []
    for t in discards:
        sh, uke = table[t]
        live = sum(max(0, 4 - seen[u]) for u in uke)
        waits = uke if sh == 0 else []
        best_tai = None
        if waits:
            hand = list(state.hands[seat])
            hand.remove(t)
            best_tai = best_tai_for_waits(hand, state.melds[seat], state.flowers[seat],
                                          state.seat_wind(seat), state.round_wind, waits)
        out.append(CandidateScore(
            tile=t, shanten_after=sh, uke_ire=uke, uke_count=live,
            danger=round(tile_danger(state, seat, t, seen), 3),
            agent_score=round(agent_scores.get(Action(ActionType.DISCARD, t), 0.0), 3),
            can_declare=t in declare_ok, waits=waits, best_tai=best_tai,
        ))
    return sorted(out, key=lambda c: (c.shanten_after, -c.uke_count, c.danger, c.tile))
