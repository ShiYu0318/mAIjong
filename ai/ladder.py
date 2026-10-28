"""Rating ladder: every agent in a pool against every other, with strength scores.

There is no public benchmark for Taiwanese 16-tile mahjong (the Computer Olympiad
programs are not released), so strength is measured inside a pool of agents. Each block
seats four agents (the four that have played least so far) and plays one deal four times,
rotating them through every seat, so the tiles and the seats even out. Blocks are appended
to a JSONL file, so a ladder can be extended later with more blocks or new agents.

Two scores come out, each with a 95% bootstrap interval over blocks:
  * points per hand above the field, fitted jointly so a strong table costs no rating;
  * Elo from a Bradley-Terry fit of "who scored more on the same block", anchored so the
    level-3 bot is 1500.

    uv run python -m ai.ladder play --pool default --blocks 3000 --out runs/ladder/main
    uv run python -m ai.ladder report runs/ladder/main
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from ai.simulate import make_agent
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game

LADDER_SEED = 910_000
ANCHOR = "lv3"

LV5_SPEC = ("rulex:flush=13,declare=4,threat_melds=3,threat_turn=12,"
            "fold_late_near=3.2,fold_ready=2.0")

# name -> agent spec; every checkpoint kept in the repository plus the built-in bots
DEFAULT_POOL: dict[str, str] = {
    "random": "random",
    "lv2": "lv2",
    "lv3": "lv3",
    "lv4": "lv4",
    "rule": "rule",
    "tuned": "tuned",
    "lv5": LV5_SPEC,
    "bc_v1": "bc:checkpoints/bc_v1.pt",
    "bc_v2": "bc:checkpoints/bc_v2.pt",
    "bc_v3": "bc:checkpoints/bc_v3.pt",
    "bc_lv5": "bc:checkpoints/bc_lv5.pt",
    "ppo_v1": "ppo:checkpoints/ppo_latest.pt",
    "ppo_v4": "ppo:checkpoints/ppo_v4.pt",
    "ppo_v5": "ppo:checkpoints/ppo_v5.pt",
    "ppo_lv5": "ppo:checkpoints/ppo_lv5.pt",
    "sb3_bc": "sb3:checkpoints/sb3_bc.zip",
    "sb3_best": "sb3:checkpoints/sb3_best.zip",
}


def schedule(names: list[str], blocks: int, start: int = 0,
             played: Counter[str] | None = None) -> list[list[str]]:
    """Lineups for blocks start..start+blocks-1: the four least-played agents, ties random."""
    rng = random.Random(LADDER_SEED + start)
    count = Counter({n: 0 for n in names})
    count.update({n: c for n, c in (played or {}).items() if n in count})
    out = []
    for _ in range(blocks):
        order = sorted(names, key=lambda n: (count[n], rng.random()))
        lineup = order[:4]
        rng.shuffle(lineup)
        count.update(lineup)
        out.append(lineup)
    return out


def play_block(lineup: list[str], specs: dict[str, str], seed: int,
               cache: dict[str, Any]) -> dict[str, Any]:
    """One deal four times, each agent taking every seat once."""
    for n in lineup:
        if n not in cache:
            cache[n] = make_agent(specs[n], seed)
    score = dict.fromkeys(lineup, 0)
    wins = dict.fromkeys(lineup, 0)
    deal_ins = dict.fromkeys(lineup, 0)
    for rot in range(4):
        seats = lineup[rot:] + lineup[:rot]
        agents = [cache[n] for n in seats]
        s = new_game(seed=seed)
        while s.phase is not Phase.ENDED:
            p = acting_players(s)[0]
            s, _ = apply_action(s, p, agents[p].act(s, p, get_legal_actions(s, p)))
        r = s.result
        assert r is not None
        for p, n in enumerate(seats):
            score[n] += r["payments"][p]
            if r["kind"] == "HU" and r["winner"] == p:
                wins[n] += 1
            if r["kind"] == "HU" and r.get("loser") == p and not r.get("self_draw"):
                deal_ins[n] += 1
    return {"seed": seed, "lineup": lineup, "score": score, "wins": wins, "deal_ins": deal_ins}


def _chunk(args: tuple[dict[str, str], list[tuple[int, list[str]]]]) -> list[dict[str, Any]]:
    specs, jobs = args
    try:
        import torch

        torch.set_num_threads(1)  # many workers side by side
    except ImportError:
        pass
    cache: dict[str, Any] = {}
    return [play_block(lineup, specs, LADDER_SEED + b, cache) for b, lineup in jobs]


def play(out: Path, specs: dict[str, str], blocks: int, workers: int, chunk: int = 20) -> None:
    out.mkdir(parents=True, exist_ok=True)
    pool_file = out / "pool.json"
    known = json.loads(pool_file.read_text()) if pool_file.exists() else {}
    for n, sp in specs.items():
        if known.get(n, sp) != sp:
            raise SystemExit(f"{n} was {known[n]!r} in this ladder, not {sp!r}; use a new name")
    known.update(specs)
    pool_file.write_text(json.dumps(known, indent=1))
    path = out / "blocks.jsonl"
    done = [json.loads(line) for line in path.open()] if path.exists() else []
    played = Counter(n for d in done for n in d["lineup"])
    lineups = schedule(sorted(known), blocks, start=len(done), played=played)
    jobs = list(enumerate(lineups, start=len(done)))
    parts = [(known, jobs[i:i + chunk]) for i in range(0, len(jobs), chunk)]
    t0 = time.time()
    finished = 0
    with ProcessPoolExecutor(workers) as ex, path.open("a") as f:
        for res in ex.map(_chunk, parts):
            for d in res:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
            f.flush()
            finished += len(res)
            rate = finished / max(1e-9, time.time() - t0)
            print(f"{finished}/{blocks} blocks, {rate:.1f}/s", flush=True)


# ------------------------------------------------------------------ ratings
def points_rating(blocks: list[dict[str, Any]], names: list[str]) -> np.ndarray:
    """θ (points per hand above the average agent): block score = 4·(θ_i − mean of table)."""
    idx = {n: k for k, n in enumerate(names)}
    rows, ys = [], []
    for d in blocks:
        for n in d["lineup"]:
            row = np.zeros(len(names))
            for m in d["lineup"]:
                row[idx[m]] -= 1.0  # 4 · (−1/4)
            row[idx[n]] += 4.0
            rows.append(row)
            ys.append(d["score"][n])
    rows.append(np.ones(len(names)))  # θ sums to zero
    ys.append(0.0)
    theta: np.ndarray = np.linalg.lstsq(np.array(rows), np.array(ys, dtype=float), rcond=None)[0]
    return theta


def elo_rating(blocks: list[dict[str, Any]], names: list[str], anchor: str = ANCHOR,
               iters: int = 400) -> np.ndarray:
    """Bradley-Terry over pairwise block results (ties half), as Elo with anchor = 1500."""
    idx = {n: k for k, n in enumerate(names)}
    k = len(names)
    w = np.full((k, k), 0.0)
    for d in blocks:
        ln = d["lineup"]
        for a in range(4):
            for b in range(a + 1, 4):
                i, j = idx[ln[a]], idx[ln[b]]
                si, sj = d["score"][ln[a]], d["score"][ln[b]]
                if si > sj:
                    w[i, j] += 1
                elif sj > si:
                    w[j, i] += 1
                else:
                    w[i, j] += 0.5
                    w[j, i] += 0.5
    w += 0.5 / k  # a light prior keeps an unbeaten or winless agent finite
    np.fill_diagonal(w, 0.0)
    n = w + w.T
    p = np.ones(k)
    for _ in range(iters):  # minorization-maximization (Hunter 2004)
        denom = (n / (p[:, None] + p[None, :])).sum(axis=1)
        p = w.sum(axis=1) / denom
        p /= np.exp(np.log(p).mean())
    elo = 400.0 * np.log10(p)
    if anchor in idx:
        elo += 1500.0 - elo[idx[anchor]]
    return elo


def report(out: Path, boot: int = 200) -> dict[str, Any]:
    blocks = [json.loads(line) for line in (out / "blocks.jsonl").open()]
    names = sorted({n for d in blocks for n in d["lineup"]})
    theta = points_rating(blocks, names)
    elo = elo_rating(blocks, names)
    rng = np.random.default_rng(0)
    bt, be = [], []
    for _ in range(boot):
        sample = [blocks[i] for i in rng.integers(0, len(blocks), len(blocks))]
        present = {n for d in sample for n in d["lineup"]}
        if present != set(names):
            continue
        bt.append(points_rating(sample, names))
        be.append(elo_rating(sample, names))
    bt_a, be_a = np.array(bt), np.array(be)
    hands: Counter[str] = Counter()
    wins: Counter[str] = Counter()
    deal_ins: Counter[str] = Counter()
    for d in blocks:
        for n in d["lineup"]:
            hands[n] += 4
            wins[n] += d["wins"][n]
            deal_ins[n] += d["deal_ins"][n]
    rows = []
    for k, n in enumerate(names):
        rows.append({
            "agent": n, "elo": round(float(elo[k]), 1),
            "elo_ci": [round(float(np.percentile(be_a[:, k], 2.5)), 1),
                       round(float(np.percentile(be_a[:, k], 97.5)), 1)],
            "points_per_hand": round(float(theta[k]), 2),
            "points_ci": [round(float(np.percentile(bt_a[:, k], 2.5)), 2),
                          round(float(np.percentile(bt_a[:, k], 97.5)), 2)],
            "hands": hands[n], "win_rate": round(wins[n] / hands[n], 4),
            "deal_in_rate": round(deal_ins[n] / hands[n], 4),
        })
    rows.sort(key=lambda r: -r["elo"])
    summary = {"blocks": len(blocks), "hands": 4 * len(blocks), "bootstrap": len(bt),
               "anchor": f"{ANCHOR} = 1500", "pool": json.loads((out / "pool.json").read_text()),
               "ratings": rows}
    (out / "ratings.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(f"{len(blocks)} blocks ({4 * len(blocks)} hands), bootstrap {len(bt)}")
    print(f"{'agent':10} {'Elo':>7} {'95% CI':>15} {'pts/hand':>9} {'95% CI':>17} "
          f"{'hands':>6} {'win':>6} {'deal-in':>7}")
    for r in rows:
        print(f"{r['agent']:10} {r['elo']:7.0f} {r['elo_ci'][0]:7.0f}–{r['elo_ci'][1]:<7.0f} "
              f"{r['points_per_hand']:9.1f} {r['points_ci'][0]:8.1f}–{r['points_ci'][1]:<8.1f} "
              f"{r['hands']:6d} {r['win_rate']:6.1%} {r['deal_in_rate']:7.1%}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--pool", default="default", help="'default', or a JSON file of name -> spec")
    p.add_argument("--add", action="append", default=[], help="extra agent as name=spec")
    p.add_argument("--blocks", type=int, default=1000)
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    r = sub.add_parser("report")
    r.add_argument("out", type=Path)
    r.add_argument("--bootstrap", type=int, default=200)
    args = ap.parse_args()
    if args.cmd == "play":
        specs = (dict(DEFAULT_POOL) if args.pool == "default"
                 else json.loads(Path(args.pool).read_text()))
        for kv in args.add:
            n, _, sp = kv.partition("=")
            specs[n] = sp
        play(args.out, specs, args.blocks, args.workers)
    else:
        report(args.out, args.bootstrap)


if __name__ == "__main__":
    main()
