"""Pick the Lv5 model by a fair head-to-head evaluation.

    python -m ai.training.promote checkpoints/bc_v2.pt checkpoints/bc_v3.pt \\
        checkpoints/ppo_latest.pt checkpoints/sb3_best.zip --hands 1000

Every candidate plays the same deals (same seeds, rotating seats) against three rule
agents; the best by win rate, then average score, is written to checkpoints/level5.json,
which create_agent(5) uses. 200-hand evaluations differ by ±3% from noise alone, so
promotion uses more hands than the periodic evaluations during training.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from ai.agents import Agent
from ai.training.evaluate import evaluate

EVAL_SEED = 50_000


def load_candidate(path: str, seed: int, temperature: float = 0.1) -> Agent:
    if path.endswith(".zip"):
        from ai.agents.sb3_agent import Sb3Agent

        return Sb3Agent(path, temperature, seed)
    from ai.agents.neural_agent import agent_from_checkpoint

    return agent_from_checkpoint(path, temperature, seed)


def _chunk(args: tuple[str, int, int]) -> dict[str, float]:
    path, hands, seed = args
    cache: dict[str, Agent] = {}

    def make(s: int) -> Agent:
        agent = cache.get("a")
        if agent is None:
            agent = cache["a"] = load_candidate(path, s)
        return agent

    r = evaluate(make, "rule", hands, seed)
    return {"hands": hands, "wins": r.win_rate * hands, "deal_ins": r.deal_in_rate * hands,
            "score": r.avg_score * hands, "tai": r.avg_tai_on_win * r.win_rate * hands}


def head_to_head(paths: list[str], hands: int = 1000, workers: int = 4,
                 seed: int = EVAL_SEED) -> list[dict[str, Any]]:
    """Win rate, deal-in rate, average score and tai for each candidate on identical deals.
    Seat rotation needs whole groups of 4 hands, so chunks are multiples of 4."""
    per = max(4, (hands // max(1, workers)) // 4 * 4)
    jobs = [(p, min(per, hands - start), seed + start)
            for p in paths for start in range(0, hands, per)]
    with ProcessPoolExecutor(workers) as pool:
        parts = list(pool.map(_chunk, jobs))
    rows = []
    for p in paths:
        mine = [r for (path, _, _), r in zip(jobs, parts, strict=True) if path == p]
        n = sum(r["hands"] for r in mine)
        wins = sum(r["wins"] for r in mine)
        rows.append({
            "path": p, "hands": n, "eval_win_rate": wins / n,
            "eval_deal_in_rate": sum(r["deal_ins"] for r in mine) / n,
            "eval_avg_score": sum(r["score"] for r in mine) / n,
            "eval_avg_tai": sum(r["tai"] for r in mine) / max(1.0, wins),
        })
    return sorted(rows, key=lambda r: (r["eval_win_rate"], r["eval_avg_score"]), reverse=True)


def promote(rows: list[dict[str, Any]], out: Path) -> dict[str, Any]:
    best = rows[0]
    record = {**best, "kind": "sb3" if best["path"].endswith(".zip") else "ppo",
              "promoted_at": time.time(), "candidates": rows}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidates", nargs="+")
    ap.add_argument("--hands", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", type=Path, default=Path("checkpoints/level5.json"))
    ap.add_argument("--dry-run", action="store_true", help="only print the table")
    args = ap.parse_args()
    missing = [c for c in args.candidates if not Path(c).exists()]
    if missing:
        raise SystemExit(f"missing: {', '.join(missing)}")
    rows = head_to_head(args.candidates, args.hands, args.workers)
    for r in rows:
        print(f"{r['eval_win_rate']:6.1%} win  {r['eval_deal_in_rate']:6.1%} deal-in  "
              f"{r['eval_avg_score']:+7.1f} score  {r['eval_avg_tai']:.2f} tai  {r['path']}")
    if not args.dry_run:
        rec = promote(rows, args.out)
        print(f"Lv5 → {rec['path']} ({args.out})")


if __name__ == "__main__":
    main()
