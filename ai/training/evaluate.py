"""Evaluate an agent against fixed opponents and track a rating (SPEC 05.7, P7-9)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ai.agents import Agent
from ai.elo import INITIAL_ELO, update_elo
from ai.simulate import make_agent, play_hand
from engine.match import ranks


@dataclass
class EvalResult:
    hands: int
    win_rate: float
    deal_in_rate: float
    avg_score: float
    avg_tai_on_win: float
    elo: float

    def as_dict(self) -> dict[str, float]:
        return {"eval_win_rate": self.win_rate, "eval_deal_in_rate": self.deal_in_rate,
                "eval_avg_score": self.avg_score, "eval_avg_tai": self.avg_tai_on_win,
                "eval_elo": self.elo}


def evaluate(make: Callable[[int], Agent], opponent: str = "rule", hands: int = 200,
             seed: int = 10_000, elo: float = INITIAL_ELO) -> EvalResult:
    """Candidate rotates through all seats against three `opponent` agents."""
    wins = deal_ins = score = tai = 0
    rating = elo
    opp_ratings = [INITIAL_ELO] * 3
    for k in range(hands):
        seat = k % 4
        agents: list[Agent] = []
        for p in range(4):
            agents.append(make(seed + k) if p == seat else make_agent(opponent, seed + k * 4 + p))
        s, _ = play_hand(agents, seed + k)
        r = s.result
        assert r is not None
        score += r["payments"][seat]
        if r["kind"] == "HU":
            if r["winner"] == seat:
                wins += 1
                tai += sum(i["tai"] for i in r["tai_breakdown"])
            elif r.get("loser") == seat and not r.get("self_draw"):
                deal_ins += 1
        order = ranks(r["payments"])
        ratings = [opp_ratings[0]] * 4
        ratings[seat] = rating
        played = [400] * 4
        played[seat] = k
        rating = update_elo(ratings, order, played)[seat]
    return EvalResult(hands, wins / hands, deal_ins / hands, score / hands,
                      tai / max(1, wins), rating)
