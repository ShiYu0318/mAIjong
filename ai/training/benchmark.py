"""Head-to-head benchmark (SPEC 05.7 B): full matches per seating, placement rates.

Each pairing is four agent specs. Every match is a whole match (one East round by
default) and the seating rotates match to match, so no spec always deals first. Per spec:
1st-4th place rates, average final score, average tai on a win, deal-in and self-draw rates.

    uv run python -m ai.training.benchmark --matches 1000
    uv run python -m ai.training.benchmark --pairing ppo:checkpoints/ppo_v5.pt rule rule rule
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai.agents import Agent
from ai.simulate import make_agent
from engine.game import Phase, acting_players, apply_action, get_legal_actions
from engine.match import finish_hand, new_match, ranks, start_hand

DEFAULT_PAIRINGS: list[list[str]] = [
    ["random"] * 4,
    ["rule"] * 4,
    ["lv4"] * 4,
    ["lv5"] * 4,
    ["random", "rule", "lv4", "lv5"],
]


@dataclass
class SpecStats:
    matches: int = 0
    places: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    final_score: int = 0
    hands: int = 0
    wins: int = 0
    self_draws: int = 0
    deal_ins: int = 0
    tai_on_win: int = 0

    def add(self, o: SpecStats) -> None:
        self.matches += o.matches
        self.places = [a + b for a, b in zip(self.places, o.places, strict=True)]
        for k in ("final_score", "hands", "wins", "self_draws", "deal_ins", "tai_on_win"):
            setattr(self, k, getattr(self, k) + getattr(o, k))

    def summary(self) -> dict[str, float]:
        m, h = max(1, self.matches), max(1, self.hands)
        return {
            "matches": self.matches,
            **{f"place_{i + 1}": self.places[i] / m for i in range(4)},
            "avg_place": sum((i + 1) * n for i, n in enumerate(self.places)) / m,
            "avg_final_score": self.final_score / m,
            "avg_tai_on_win": self.tai_on_win / max(1, self.wins),
            "win_rate": self.wins / h,
            "deal_in_rate": self.deal_ins / h,
            "self_draw_rate": self.self_draws / h,
        }


def play_match(agents: list[Agent], seed: int, rounds: int
               ) -> tuple[list[int], list[dict[str, Any]]]:
    """Final scores and the per-hand results of one match."""
    m = new_match(rounds=rounds)
    results: list[dict[str, Any]] = []
    k = 0
    while not m.finished:
        s = start_hand(m, seed=seed * 1000 + k)
        while s.phase is not Phase.ENDED:
            p = acting_players(s)[0]
            s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
        assert s.result is not None
        results.append(s.result)
        m = finish_hand(m, s)
        k += 1
    return list(m.scores), results


def _chunk(args: tuple[list[str], list[int], int]) -> dict[str, SpecStats]:
    specs, match_ids, rounds = args
    # one agent per slot, reused across matches (neural checkpoints load once per worker)
    slots = [make_agent(spec, 7919 * (i + 1)) for i, spec in enumerate(specs)]
    out: dict[str, SpecStats] = {spec: SpecStats() for spec in specs}
    for mid in match_ids:
        r = mid % 4  # seat p gets slot (p + r) % 4
        order = [(p + r) % 4 for p in range(4)]
        scores, hands = play_match([slots[i] for i in order], seed=mid, rounds=rounds)
        place = ranks(scores)
        for p in range(4):
            st = out[specs[order[p]]]
            st.matches += 1
            st.places[place[p] - 1] += 1
            st.final_score += scores[p]
        for res in hands:
            for p in range(4):
                out[specs[order[p]]].hands += 1
            if res["kind"] == "DRAW":
                continue
            w = out[specs[order[res["winner"]]]]
            w.wins += 1
            w.tai_on_win += sum(i["tai"] for i in res["tai_breakdown"])
            if res["self_draw"]:
                w.self_draws += 1
            elif res.get("loser") is not None:
                out[specs[order[res["loser"]]]].deal_ins += 1
    return out


def benchmark(specs: list[str], matches: int, rounds: int = 1, workers: int = 1,
              seed: int = 0) -> dict[str, dict[str, float]]:
    ids = list(range(seed, seed + matches))
    n = max(1, workers)
    jobs = [(specs, ids[i::n], rounds) for i in range(n) if ids[i::n]]
    total: dict[str, SpecStats] = {spec: SpecStats() for spec in specs}
    parts: Iterator[dict[str, SpecStats]]
    if n == 1:
        parts = map(_chunk, jobs)
        for part in parts:
            for spec, st in part.items():
                total[spec].add(st)
    else:
        with ProcessPoolExecutor(max_workers=n) as pool:
            for part in pool.map(_chunk, jobs):
                for spec, st in part.items():
                    total[spec].add(st)
    return {spec: st.summary() for spec, st in total.items()}


def table(name: str, summary: dict[str, dict[str, float]]) -> str:
    lines = [f"### {name}", "",
             "| agent | 1st | 2nd | 3rd | 4th | avg place | avg score | win | tai/win "
             "| deal-in | tsumo |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for spec, s in summary.items():
        lines.append(
            f"| {spec} | {s['place_1']:.1%} | {s['place_2']:.1%} | {s['place_3']:.1%} | "
            f"{s['place_4']:.1%} | {s['avg_place']:.2f} | {s['avg_final_score']:+.0f} | "
            f"{s['win_rate']:.1%} | {s['avg_tai_on_win']:.2f} | {s['deal_in_rate']:.1%} | "
            f"{s['self_draw_rate']:.1%} |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--matches", type=int, default=1000, help="matches per pairing")
    ap.add_argument("--rounds", type=int, default=1, help="rounds per match (1 = East only)")
    ap.add_argument("--pairing", nargs=4, action="append", metavar="SPEC",
                    help="four agent specs; repeat for more pairings (default: SPEC 05.7 set)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", type=Path, default=None, help="also write the numbers here")
    args = ap.parse_args()
    report: dict[str, Any] = {}
    for specs in args.pairing or DEFAULT_PAIRINGS:
        name = " × ".join(specs) if len(set(specs)) > 1 else f"{specs[0]} ×4"
        summary = benchmark(specs, args.matches, args.rounds, args.workers, args.seed)
        report[name] = summary
        print(table(name, summary) + "\n", flush=True)
    if args.json:
        args.json.write_text(json.dumps({"matches": args.matches, "rounds": args.rounds,
                                         "pairings": report}, indent=2))


__all__ = ["SpecStats", "benchmark", "play_match", "table"]

if __name__ == "__main__":
    main()
