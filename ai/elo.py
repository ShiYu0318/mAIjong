"""Tenhou-style four-player rating (SPEC 07.2), shared by training and the arena."""

from __future__ import annotations

BASE_SCORE = (30, 10, -10, -30)
RATING_DIV = 40
INITIAL_ELO = 1500.0


def games_coeff(games_played: int) -> float:
    """Newcomers move faster; fixed at 0.2 after 400 games."""
    return max(1.0 - games_played * 0.002, 0.2)


def update_elo(ratings: list[float], ranks: list[int], games_played: list[int]) -> list[float]:
    """ranks are 1-4 per seat; ties should already be broken by seat order."""
    table_avg = sum(ratings) / len(ratings)
    return [
        r + (BASE_SCORE[rank - 1] + (table_avg - r) / RATING_DIV) * games_coeff(g)
        for r, rank, g in zip(ratings, ranks, games_played, strict=True)
    ]
