"""Cross-entropy search over the rule agent's parameters, on fresh deals every generation.

The earlier tuners (ai.training.tune, coordinate ascent) compared candidates on the same
deals again and again, so they ended up fitting those deals: their "significant" gains
vanished on deals they had never seen. Here every generation draws new deals that no other
generation uses, all candidates of a generation share them (and their seats), and the
baseline plays each deal once for all of them. The search distribution moves toward the
best few of each generation, which averages the noise out over generations instead of
trusting any single comparison. Confirm the result with ai.training.duplicate --seed on
deals outside the search range.

    uv run python -m ai.training.cem_tune --generations 40 --out runs/cem/v1
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

import numpy as np

from ai.agents.rule_agent import RuleAgent, RuleParams
from ai.simulate import make_agent
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game

CEM_SEED = 20_000_000  # generation g plays deals CEM_SEED + g * 100_000 + k

# name, low, high: the search box (the defaults of RuleParams sit inside it)
SPACE: list[tuple[str, float, float]] = [
    ("w_shanten", 4.0, 20.0),
    ("w_live", 0.02, 0.4),
    ("honor_discard", 0.0, 0.3),
    ("ting_bonus", 0.0, 3.0),
    ("value_pon", 0.0, 3.0),
    ("flush", 9.0, 15.0),  # below 10.5 → 0 (off), else the tile count
    ("flush_far", 0.0, 10.0),
    ("flush_near", 0.0, 25.0),
    ("fold_ready", 0.0, 12.0),
    ("fold_one", 2.0, 30.0),
    ("fold_far", 10.0, 80.0),
    ("late_wall", 10.0, 40.0),
    ("fold_late_near", 0.0, 8.0),
    ("fold_late_far", 0.0, 15.0),
    ("threat_melds", 1.5, 4.5),  # above 4 → 0 (off)
    ("threat_turn", 6.0, 20.0),  # above 18 → 0 (off)
    ("threat_scale", 0.1, 1.0),
    ("declare", 0.5, 7.5),  # below 1.5 → "always", else only with that many unseen waits
]
INTS = {"flush", "late_wall", "threat_melds", "threat_turn", "declare"}


def to_params(x: np.ndarray) -> RuleParams:
    """A point of the unit cube → RuleParams. Off-switches are decided on the raw value,
    then integers are rounded."""
    raw = {name: lo + float(u) * (hi - lo)
           for (name, lo, hi), u in zip(SPACE, np.clip(x, 0.0, 1.0), strict=True)}
    values: dict[str, Any] = {n: (int(round(v)) if n in INTS else round(v, 4))
                              for n, v in raw.items()}
    if raw["flush"] < 10.5:
        values["flush"] = 0
    if raw["threat_melds"] > 4.25:
        values["threat_melds"] = 0
    if raw["threat_turn"] > 18.5:
        values["threat_turn"] = 0
    values["declare"] = "always" if raw["declare"] < 1.5 else values["declare"]
    return RuleParams(**values)


OFF = {"flush": 10.0, "threat_melds": 4.4, "threat_turn": 19.5}


def from_params(p: RuleParams) -> np.ndarray:
    """RuleParams → unit cube (used to start the search at a known agent)."""
    d = asdict(p)
    out = []
    for name, lo, hi in SPACE:
        v = d[name]
        if name in OFF and v == 0:
            v = OFF[name]
        elif name == "declare":
            v = 1.0 if v in ("always", "never") else float(v)
        out.append((float(v) - lo) / (hi - lo))
    return np.clip(np.array(out), 0.0, 1.0)


def _play(agent: Any, opponent: list[str], seed: int, seat: int) -> int:
    agents = [agent if p == seat else make_agent(opponent[(seed + p) % len(opponent)], seed * 4 + p)
              for p in range(4)]
    s = new_game(seed=seed)
    while s.phase is not Phase.ENDED:
        p = acting_players(s)[0]
        s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
    assert s.result is not None
    return int(s.result["payments"][seat])


def _chunk(args: tuple[list[dict[str, Any]], str, list[str], list[int]]) -> np.ndarray:
    """Scores (n_candidates + 1, n_seeds): the baseline in the last row."""
    cands, base, opponent, seeds = args
    agents = [RuleAgent(0.0, 1, params=RuleParams(**c)) for c in cands] + [make_agent(base, 1)]
    out = np.zeros((len(agents), len(seeds)))
    for j, s in enumerate(seeds):
        for i, a in enumerate(agents):
            out[i, j] = _play(a, opponent, s, s % 4)
    return out


def evaluate(cands: list[RuleParams], base: str, opponent: list[str], seeds: list[int],
             workers: int) -> np.ndarray:
    """Per candidate, the mean paired score difference against the baseline."""
    raw = [asdict(c) for c in cands]
    n = max(1, min(workers * 3, len(seeds)))
    jobs = [(raw, base, opponent, seeds[i::n]) for i in range(n)]
    with ProcessPoolExecutor(workers) as ex:
        parts = list(ex.map(_chunk, jobs))
    scores = np.concatenate(parts, axis=1)
    diff: np.ndarray = (scores[:-1] - scores[-1]).mean(axis=1)
    return diff


def search(out: Path, generations: int, pop: int, elite: int, deals: int, base: str,
           opponent: list[str], workers: int, start: RuleParams, sigma: float = 0.15) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    mean = from_params(start)
    std = np.full(len(SPACE), sigma)
    log = out / "generations.jsonl"
    for g in range(generations):
        t0 = time.time()
        xs = [mean] + [np.clip(mean + std * rng.standard_normal(len(SPACE)), 0, 1)
                       for _ in range(pop - 1)]  # keep the current mean in the race
        cands = [to_params(x) for x in xs]
        seeds = [CEM_SEED + g * 100_000 + k for k in range(deals)]
        fit = evaluate(cands, base, opponent, seeds, workers)
        order = np.argsort(-fit)
        top = np.array([xs[i] for i in order[:elite]])
        mean = 0.7 * top.mean(axis=0) + 0.3 * mean  # smoothed: one noisy generation can't jump far
        std = np.maximum(0.7 * top.std(axis=0) + 0.3 * std, 0.03)
        rec = {"gen": g, "seconds": round(time.time() - t0), "mean_fit": float(fit[0]),
               "best_fit": float(fit[order[0]]), "fits": [round(float(f), 2) for f in fit],
               "mean": asdict(to_params(mean)), "std": [round(float(v), 3) for v in std]}
        with log.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        (out / "best.json").write_text(json.dumps(asdict(to_params(mean)), indent=1))
        print(f"gen {g}: current mean {fit[0]:+.1f}, best {fit[order[0]]:+.1f} points/hand vs "
              f"{base} ({rec['seconds']}s), spread {std.mean():.3f}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--generations", type=int, default=40)
    ap.add_argument("--pop", type=int, default=12)
    ap.add_argument("--elite", type=int, default=4)
    ap.add_argument("--deals", type=int, default=3000)
    ap.add_argument("--baseline", default="rule")
    ap.add_argument("--opponent", default="rule|rulex:declare=never|rulex:calls=near|lv4")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    known = {f.name for f in fields(RuleParams)}
    assert all(name in known for name, _, _ in SPACE)
    search(args.out, args.generations, args.pop, args.elite, args.deals, args.baseline,
           args.opponent.split("|"), args.workers, RuleParams())


if __name__ == "__main__":
    main()
