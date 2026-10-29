"""Rating ladder: balanced lineups, ratings that recover a known order, a real mini run."""

from __future__ import annotations

import json
import random
from collections import Counter

from ai.ladder import LV5_SPEC, elo_rating, play_block, points_rating, report, schedule


def test_schedule_spreads_play_evenly():
    names = [f"a{i}" for i in range(9)]
    lineups = schedule(names, 90)
    assert all(len(set(ln)) == 4 for ln in lineups)
    seen = Counter(n for ln in lineups for n in ln)
    assert max(seen.values()) - min(seen.values()) <= 1
    # extending a ladder keeps balancing from where it stopped
    more = schedule(names, 9, start=90, played=seen)
    seen.update(n for ln in more for n in ln)
    assert max(seen.values()) - min(seen.values()) <= 1


def _synthetic(strength: dict[str, float], blocks: int) -> list[dict]:
    rng = random.Random(1)
    names = sorted(strength)
    out = []
    for lineup in schedule(names, blocks):
        mean = sum(strength[n] for n in lineup) / 4
        score = {n: round(4 * (strength[n] - mean) + rng.gauss(0, 30)) for n in lineup}
        out.append({"lineup": lineup, "score": score})
    return out


def test_ratings_recover_a_known_order():
    strength = {"weak": -40.0, "lv3": 0.0, "good": 15.0, "best": 30.0, "mid": 5.0}
    blocks = _synthetic(strength, 600)
    names = sorted(strength)
    theta = dict(zip(names, points_rating(blocks, names), strict=True))
    elo = dict(zip(names, elo_rating(blocks, names), strict=True))
    order = sorted(strength, key=strength.get)
    assert sorted(theta, key=theta.get) == order
    assert sorted(elo, key=elo.get) == order
    assert abs(elo["lv3"] - 1500) < 1e-6
    # θ is in the same units as the truth (points per hand relative to the field)
    shift = sum(strength.values()) / len(strength)
    assert all(abs(theta[n] - (strength[n] - shift)) < 4 for n in names)


def test_a_real_block_and_report(tmp_path):
    # only specs that need no checkpoint files (CI has none)
    specs = {"random": "random", "rule": "rule", "lv2": "lv2", "lv3": "lv3", "lv5": LV5_SPEC}
    blocks = []
    cache: dict = {}
    for b, lineup in enumerate(schedule(sorted(specs), 30)):
        d = play_block(lineup, specs, 5000 + b, cache)
        assert sum(d["score"].values()) == 0  # four rotations of a zero-sum deal
        blocks.append(d)
    (tmp_path / "blocks.jsonl").write_text("\n".join(json.dumps(d) for d in blocks) + "\n")
    (tmp_path / "pool.json").write_text(json.dumps(specs))
    summary = report(tmp_path, boot=20)
    elo = {r["agent"]: r["elo"] for r in summary["ratings"]}
    assert elo["random"] < min(elo["rule"], elo["lv5"])
    assert (tmp_path / "ratings.json").exists()
