"""Nightly simulation checks (SPEC 11).

1. Soak: N hands between random agents. Every hand must end, keep the scores zero-sum,
   keep all 144 tiles accounted for, and re-run to the same result from its seed + actions.
2. Pairs: every pair of agents plays M hands seated A-B-A-B (seats rotate); each side's
   win rate must fall in the expected range. Lv4/Lv5 fall back to the rule agent when no
   checkpoint is present (as in CI), which keeps the ranges valid.

    uv run python scripts/nightly_sim.py --soak 1000 --pairs 100
"""

from __future__ import annotations

import argparse
import itertools
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.agents import RandomAgent  # noqa: E402
from ai.simulate import play_hand, run_batch  # noqa: E402
from engine.actions import decode_action  # noqa: E402
from engine.game import apply_action, new_game  # noqa: E402

AGENTS = ["random", "rule", "lv4", "lv5"]


def soak(n: int, seed0: int = 0) -> list[str]:
    errors: list[str] = []
    for seed in range(seed0, seed0 + n):
        try:
            s, actions = play_hand([RandomAgent(seed * 4 + i) for i in range(4)], seed)
        except Exception as exc:  # a crash is exactly what the soak is looking for
            errors.append(f"hand {seed}: crashed: {exc!r}")
            continue
        if s.result is None:
            errors.append(f"hand {seed}: ended without a result")
            continue
        if sum(s.scores) != 0:
            errors.append(f"hand {seed}: scores not zero-sum {s.scores}")
        tiles = len(s.wall) + sum(map(len, s.hands)) + sum(map(len, s.flowers)) \
            + sum(map(len, s.discards)) + sum(len(m.tiles) for ms in s.melds for m in ms)
        if tiles != 144:
            errors.append(f"hand {seed}: {tiles} tiles accounted for, not 144")
        again = new_game(seed=seed)
        for p, aid in actions:
            again, _ = apply_action(again, p, decode_action(aid))
        if again.result != s.result:
            errors.append(f"hand {seed}: replay reached a different result")
    return errors


def expected(a: str, b: str, wa: float, wb: float) -> str | None:
    """None when the win rates are plausible for this pairing, else the reason."""
    if "random" in (a, b) and a != b:
        strong, weak = (wb, wa) if a == "random" else (wa, wb)
        if strong < 0.25 or weak > 0.05:
            return "a real agent should win >= 25% and random <= 5%"
        return None
    if not (0.10 <= wa <= 0.40 and 0.10 <= wb <= 0.40):
        return "comparable agents should each win 10-40%"
    return None


def pairs(n: int, workers: int) -> tuple[list[str], list[str]]:
    rows, errors = [], []
    for a, b in itertools.combinations(AGENTS, 2):
        r = run_batch([a, b, a, b], n, seed=10_000, workers=workers)
        w = [st.wins / max(1, st.hands) for st in r.seats]
        wa, wb = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        problem = expected(a, b, wa, wb)
        rows.append(f"| {a} | {b} | {wa:.1%} | {wb:.1%} | {r.draws / max(1, r.hands):.1%} | "
                    f"{'ok' if problem is None else problem} |")
        if problem:
            errors.append(f"{a} vs {b}: {wa:.1%} / {wb:.1%}: {problem}")
    return rows, errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--soak", type=int, default=1000, help="random-agent hands")
    ap.add_argument("--pairs", type=int, default=100, help="hands per agent pair")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()

    t0 = time.time()
    soak_errors = soak(args.soak)
    t_soak = time.time() - t0
    rows, pair_errors = pairs(args.pairs, args.workers)
    lines = [
        "## Nightly simulation",
        f"Soak: {args.soak} random hands in {t_soak:.0f}s, {len(soak_errors)} problems.",
        "",
        f"Pairs: {args.pairs} hands each, seated A-B-A-B.",
        "",
        "| A | B | A wins | B wins | draws | check |",
        "|---|---|---|---|---|---|",
        *rows,
    ]
    if soak_errors or pair_errors:
        lines += ["", "### Problems", *[f"- {e}" for e in (soak_errors[:50] + pair_errors)]]
    report = "\n".join(lines)
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 1 if soak_errors or pair_errors else 0


if __name__ == "__main__":
    sys.exit(main())
