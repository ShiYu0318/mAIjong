"""Duplicate (paired) evaluation: is a candidate really better than a baseline?

Every deal is played twice from the same seed, once with the candidate and once with the
baseline in the same seat (rotating seats deal by deal), against the same opponents. The
per-deal score difference cancels most of the luck of the deal, so far fewer hands are
needed than when two averages are compared separately.

    uv run python -m ai.training.duplicate rulex:declare=4 --baseline rule --hands 2000
"""

from __future__ import annotations

import argparse
import math
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from ai.simulate import make_agent
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game

DUP_SEED = 70_000


def _play(spec: str, opponent: str, seed: int, seat: int, cache: dict[str, Any]) -> dict[str, Any]:
    key = f"{spec}@{seat}"
    if key not in cache:
        cache[key] = make_agent(spec, seed)
    pool = opponent.split("|")  # several styles rotate over seats and deals
    agents = [cache[key] if p == seat else make_agent(pool[(seed + p) % len(pool)], seed * 4 + p)
              for p in range(4)]
    s = new_game(seed=seed)
    while s.phase is not Phase.ENDED:
        p = acting_players(s)[0]
        s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
    assert s.result is not None
    r = s.result
    return {"score": r["payments"][seat],
            "win": int(r["kind"] == "HU" and r["winner"] == seat),
            "deal_in": int(r["kind"] == "HU" and r.get("loser") == seat and not r.get("self_draw"))}


def _chunk(args: tuple[str, str, str, list[int]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    cand, base, opponent, seeds = args
    cache: dict[str, Any] = {}
    return [(_play(cand, opponent, s, s % 4, cache), _play(base, opponent, s, s % 4, cache))
            for s in seeds]


@dataclass
class PairedResult:
    hands: int
    mean_diff: float
    se: float
    cand: dict[str, float]
    base: dict[str, float]

    @property
    def t(self) -> float:
        return self.mean_diff / self.se if self.se > 0 else 0.0

    def line(self, cand: str, base: str) -> str:
        c, b = self.cand, self.base
        return (f"{cand} vs {base}: {self.mean_diff:+.1f} points/hand ± {self.se:.1f} "
                f"(t = {self.t:+.2f}, {self.hands} deals) | win {c['win']:.1%} vs {b['win']:.1%}, "
                f"deal-in {c['deal_in']:.1%} vs {b['deal_in']:.1%}")


def paired(cand: str, base: str = "rule", hands: int = 2000, opponent: str = "rule",
           workers: int = 4, seed: int = DUP_SEED) -> PairedResult:
    seeds = list(range(seed, seed + hands))
    n = max(1, workers)
    jobs = [(cand, base, opponent, seeds[i::n]) for i in range(n) if seeds[i::n]]
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if n == 1:
        for j in jobs:
            pairs += _chunk(j)
    else:
        with ProcessPoolExecutor(n) as pool:
            for part in pool.map(_chunk, jobs):
                pairs += part
    diffs = [c["score"] - b["score"] for c, b in pairs]
    m = len(diffs)
    mean = sum(diffs) / m
    var = sum((d - mean) ** 2 for d in diffs) / max(1, m - 1)

    def rates(side: int) -> dict[str, float]:
        return {k: sum(p[side][k] for p in pairs) / m for k in ("win", "deal_in", "score")}

    return PairedResult(m, mean, math.sqrt(var / m), rates(0), rates(1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("candidates", nargs="+")
    ap.add_argument("--baseline", default="rule")
    ap.add_argument("--opponent", default="rule",
                    help="the three other seats; a|b|c rotates several styles")
    ap.add_argument("--hands", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    for cand in args.candidates:
        res = paired(cand, args.baseline, args.hands, args.opponent, args.workers)
        print(res.line(cand, args.baseline), flush=True)


if __name__ == "__main__":
    main()
