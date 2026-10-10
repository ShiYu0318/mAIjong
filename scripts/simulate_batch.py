"""Run batch simulations and print per-seat statistics.

Examples:
    uv run python scripts/simulate_batch.py --agents rule random random random -n 1000
    uv run python scripts/simulate_batch.py --agents rule rule rule rule -n 100000 \
        --workers 8 --save data/bc/rule_selfplay.jsonl.gz
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.simulate import run_batch  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--agents", nargs=4, default=["rule", "random", "random", "random"])
    ap.add_argument("-n", "--hands", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--save", type=Path, default=None, help="write compact replays (.jsonl.gz)")
    ap.add_argument("--no-rotate", action="store_true", help="keep agents on fixed seats")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = ap.parse_args()
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    def progress(done: int) -> None:
        print(f"\r{done}/{args.hands} hands  {done / max(1e-9, time.time() - t0):.0f}/s",
              end="", file=sys.stderr)

    res = run_batch(args.agents, args.hands, args.seed, args.workers, args.save,
                    rotate=not args.no_rotate, progress=progress)
    print(file=sys.stderr)
    summary = res.summary()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"{summary['hands']} hands, draw rate {summary['draw_rate']:.1%}")
    print(f"{'agent':<12}{'win':>8}{'tsumo':>8}{'deal-in':>9}{'avg tai':>9}{'avg score':>11}")
    for s in summary["seats"]:
        print(f"{s['agent']:<12}{s['win_rate']:>8.1%}{s['self_draw_rate']:>8.1%}"
              f"{s['deal_in_rate']:>9.1%}{s['avg_tai_on_win']:>9.2f}{s['avg_score']:>11.1f}")


if __name__ == "__main__":
    main()
