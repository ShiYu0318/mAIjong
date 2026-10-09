"""Match (一將) progression: dealer rotation, dealer streak and round wind."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.game import GameState, Phase, new_game
from engine.score import ScoringRules

MAX_DEALER_STREAK = 9


@dataclass
class MatchState:
    first_dealer: int = 0
    rounds: int = 4  # 圈數: 1-4 (4 = 一將)
    dealer: int = 0
    dealer_streak: int = 0
    round_wind: int = 0
    scores: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    hands_played: int = 0
    finished: bool = False
    rules: ScoringRules = field(default_factory=ScoringRules)
    history: list[dict[str, Any]] = field(default_factory=list)


def new_match(
    first_dealer: int = 0, rounds: int = 4, rules: ScoringRules | None = None
) -> MatchState:
    if not 1 <= rounds <= 4:
        raise ValueError("rounds must be 1-4")
    return MatchState(first_dealer, rounds, first_dealer, rules=rules or ScoringRules())


def start_hand(m: MatchState, seed: int | None = None) -> GameState:
    if m.finished:
        raise ValueError("match already finished")
    return new_game(
        seed,
        dealer=m.dealer,
        round_wind=m.round_wind,
        dealer_streak=m.dealer_streak,
        scores=m.scores,
        rules=m.rules,
    )


def finish_hand(m: MatchState, g: GameState) -> MatchState:
    """Return the match state after a finished hand."""
    if g.phase is not Phase.ENDED or g.result is None:
        raise ValueError("hand is not finished")
    out = MatchState(
        first_dealer=m.first_dealer,
        rounds=m.rounds,
        dealer=m.dealer,
        dealer_streak=m.dealer_streak,
        round_wind=m.round_wind,
        scores=list(g.scores),
        hands_played=m.hands_played + 1,
        rules=m.rules,
        history=[*m.history, {"dealer": m.dealer, "streak": m.dealer_streak,
                              "round_wind": m.round_wind, "result": g.result}],
    )
    dealer_keeps = g.result["kind"] == "DRAW" or g.result.get("winner") == m.dealer
    if dealer_keeps and m.dealer_streak < MAX_DEALER_STREAK:
        out.dealer_streak += 1
        return out
    out.dealer = (m.dealer + 1) % 4
    out.dealer_streak = 0
    if out.dealer == m.first_dealer:
        out.round_wind += 1
        if out.round_wind >= m.rounds:
            out.finished = True
    return out


def ranks(scores: list[int]) -> list[int]:
    """1-based placement per seat; ties broken by seat order."""
    order = sorted(range(4), key=lambda p: (-scores[p], p))
    out = [0] * 4
    for place, p in enumerate(order, start=1):
        out[p] = place
    return out
