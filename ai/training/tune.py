"""Tune the rule agent's parameters by coordinate ascent with duplicate evaluation.

Each round tries, one parameter at a time, a few alternative values against the current
best on fresh deals (paired, same seats, a mixed pool of opponent styles so the result is
not an exploit of one bot). The best alternative is kept only when it wins by a paired
t >= --t, which is set above 2 because many alternatives are tried per round.

    uv run python -m ai.training.tune --rounds 3 --hands 3000
The best parameters go to checkpoints/rule_tuned.json (load with the `tuned` agent spec).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from ai.agents.rule_agent import RuleParams
from ai.training.duplicate import paired

POOL = "rule|rulex:declare=never|rulex:calls=near"
CHOICES: dict[str, list[Any]] = {
    "declare": ["always", "never", 3, 4, 5, 6],
    "calls": ["shanten", "near"],
    "flush": [0, 11, 12, 13, 14],
    "late_wall": [12, 18, 24, 30, 36],
    "value_pon": [0.0, 1.0, 3.0],
}
SCALED = ["w_live", "honor_discard", "ting_bonus", "flush_far", "flush_near", "fold_ready",
          "fold_one", "fold_far", "fold_late_near", "fold_late_far"]


def spec(params: dict[str, Any]) -> str:
    defaults = asdict(RuleParams())
    diff = {k: v for k, v in params.items() if v != defaults[k]}
    return "rulex:" + ",".join(f"{k}={v}" for k, v in sorted(diff.items()))


def alternatives(name: str, value: Any) -> list[Any]:
    if name in CHOICES:
        return [v for v in CHOICES[name] if v != value]
    if name in SCALED:
        base = value if value else 0.5
        return sorted({round(base * 0.5, 3), round(base * 1.6, 3)} - {value})
    return []


def tune(rounds: int, hands: int, workers: int, t_min: float, start: dict[str, Any],
         log: Path, seed: int) -> dict[str, Any]:
    best = {**asdict(RuleParams()), **start}
    log.parent.mkdir(parents=True, exist_ok=True)
    names = [f.name for f in fields(RuleParams) if alternatives(f.name, best[f.name])]
    block = seed
    for rnd in range(1, rounds + 1):
        changed = False
        for name in names:
            trials = []
            for alt in alternatives(name, best[name]):
                cand = {**best, name: alt}
                block += hands
                res = paired(spec(cand), spec(best), hands, POOL, workers, seed=block)
                trials.append((res.t, alt, res))
                with log.open("a") as fh:
                    fh.write(json.dumps({"round": rnd, "param": name, "value": alt,
                                         "from": best[name], "diff": res.mean_diff,
                                         "se": res.se, "t": res.t, "time": time.time()}) + "\n")
                print(f"r{rnd} {name}={alt!r:>9} vs {best[name]!r:>9}: {res.mean_diff:+6.1f} "
                      f"± {res.se:4.1f} (t {res.t:+.2f})", flush=True)
            t, alt, res = max(trials, key=lambda x: x[0])
            if t >= t_min:
                print(f"  -> keep {name}={alt!r}", flush=True)
                best[name] = alt
                changed = True
        out = Path("checkpoints/rule_tuned.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"params": best, "spec": spec(best), "round": rnd}, indent=2))
        print(f"round {rnd} done: {spec(best)}", flush=True)
        if not changed:
            break
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--hands", type=int, default=3000, help="paired deals per comparison")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--t", type=float, default=2.5, help="paired t needed to keep a change")
    ap.add_argument("--start", default="", help="rulex-style overrides to start from")
    ap.add_argument("--seed", type=int, default=100_000)
    ap.add_argument("--log", type=Path, default=Path("runs/tune/tune.jsonl"))
    args = ap.parse_args()
    start: dict[str, Any] = {}
    for kv in filter(None, args.start.split(",")):
        k, _, v = kv.partition("=")
        start[k] = int(v) if v.lstrip("-").isdigit() else (
            float(v) if v.replace(".", "", 1).isdigit() else v)
    best = tune(args.rounds, args.hands, args.workers, args.t, start, args.log, args.seed)
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    main()
