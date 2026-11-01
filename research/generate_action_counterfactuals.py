"""Fair-information teacher, exact action IDs, grouped episodes and pre-action common worlds."""

import argparse
import fcntl
import hashlib
import json
import multiprocessing
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from ai.agents import LEVEL5_PARAMS, RuleAgent
from ai.features import encode, mask_for
from ai.history import encode_public_history
from engine.actions import encode_action
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game
from research.action_counterfactuals import action_candidates, label_actions
from research.offline_data import fold_for_seed

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research-action-q-v2-pilot-01"


def initialize():
    torch.set_num_threads(1)


def collect(task):
    seed, rate, worlds, limit, history_length = task
    rng = random.Random(seed)
    agents = [RuleAgent(0.0, seed * 4 + p, params=LEVEL5_PARAMS) for p in range(4)]
    state, trace, rows = new_game(seed=seed), [], []
    phases, action_types, rollouts = {}, {}, 0
    start = time.time()
    while state.phase is not Phase.ENDED:
        seat = acting_players(state)[0]
        legal = get_legal_actions(state, seat)
        teacher = agents[seat].act(state, seat, legal)
        if len(legal) > 1 and rng.random() < rate:
            actions = action_candidates(agents[seat], state, seat, legal, teacher, limit)
            q, se, samples = label_actions(
                state, seat, actions, seed=seed * 10000 + len(trace), worlds=worlds
            )
            tiles, scalars = encode(state, seat)
            history, history_mask = encode_public_history(state, seat, history_length)
            legal_mask = mask_for(state, seat)
            candidate_mask = np.isfinite(q)
            aid = encode_action(teacher)
            if not candidate_mask[aid] or (candidate_mask & ~legal_mask).any():
                raise ValueError("Counterfactual teacher/candidate legality contract failed")
            rows.append(
                {
                    "tiles": tiles.astype(np.float16),
                    "scalars": scalars.astype(np.float16),
                    "history": history.astype(np.uint8),
                    "history_mask": history_mask,
                    "legal_mask": legal_mask,
                    "candidate_mask": candidate_mask,
                    "q": q,
                    "paired_wall_se": se,
                    "world_payments": samples,
                    "teacher_action": np.int64(aid),
                    "seat": np.int8(seat),
                    "hand_seed": np.int64(seed),
                    "action_index": np.int32(len(trace)),
                }
            )
            phases[state.phase.value] = phases.get(state.phase.value, 0) + 1
            action_types[teacher.type.value] = action_types.get(teacher.type.value, 0) + 1
            rollouts += len(actions) * worlds
        trace.append([seat, encode_action(teacher)])
        state, _ = apply_action(state, seat, teacher)
    arrays = {key: np.stack([row[key] for row in rows]) for key in rows[0]} if rows else None
    return {
        "seed": seed,
        "record": {"seed": seed, "actions": trace, "result": state.result},
        "arrays": arrays,
        "rows": len(rows),
        "rollouts": rollouts,
        "phases": phases,
        "teacher_action_types": action_types,
        "seconds": time.time() - start,
    }


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def main(
    out=OUT,
    hands=64,
    seed_start=2026150000,
    rate=0.08,
    worlds=4,
    limit=6,
    history_length=128,
    workers=2,
):
    if (
        min(hands, worlds, history_length, workers) < 1
        or not 0 < rate <= 1
        or not 2 <= limit <= 108
    ):
        raise ValueError("Invalid collection budget or schema parameters")
    out.mkdir(parents=True, exist_ok=False)
    with (out / "runner.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sources = [
            *sorted(ROOT.glob("ai/**/*.py")),
            *sorted(ROOT.glob("engine/**/*.py")),
            *sorted(ROOT.glob("sdk/maijong_sdk/*.py")),
            ROOT / "backend/ws/view.py",
            ROOT / "research/action_counterfactuals.py",
            ROOT / "research/offline_data.py",
            Path(__file__).resolve(),
        ]
        plan = {
            "information_contract": "visible-v2-ignore-opponent-concealed-kong-identities",
            "hands": hands,
            "seed_start": seed_start,
            "sample_rate": rate,
            "worlds": worlds,
            "candidate_limit": limit,
            "history_length": history_length,
            "workers": workers,
            "teacher_params": asdict(LEVEL5_PARAMS),
            "sources": {str(path.relative_to(ROOT)): sha(path) for path in sources},
            "limitations": [
                "small collection pilot; no trained-strength claim",
                "oracle opponents hands used only to generate training targets",
                "future-wall SE excludes hidden-hand and model uncertainty",
                "student observes masked features/history/own legal actions only",
                "teacher-policy continuation, not an optimal value",
            ],
        }
        write(out / "manifest.json", plan)
        for source in sources:
            target = out / "source" / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        stats = {
            "hands": 0,
            "samples": 0,
            "rollouts": 0,
            "files": [],
            "phase_counts": {},
            "teacher_action_counts": {},
            "started": time.time(),
        }
        tasks = [
            (
                seed,
                plan["sample_rate"],
                plan["worlds"],
                plan["candidate_limit"],
                plan["history_length"],
            )
            for seed in range(plan["seed_start"], plan["seed_start"] + plan["hands"])
        ]
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=initialize,
            mp_context=multiprocessing.get_context("spawn"),
        ) as pool:
            for result in pool.map(collect, tasks, chunksize=1):
                seed = result["seed"]
                record = out / f"hand-{seed}.json"
                write(record, result["record"])
                item = {
                    "seed": seed,
                    "fold": fold_for_seed(seed),
                    "record": record.name,
                    "record_sha256": sha(record),
                    "samples": result["rows"],
                }
                if result["arrays"] is not None:
                    path = out / f"hand-{seed}.npz"
                    np.savez_compressed(path, **result["arrays"])
                    item.update(path=path.name, sha256=sha(path))
                stats["files"].append(item)
                stats["hands"] += 1
                stats["samples"] += result["rows"]
                stats["rollouts"] += result["rollouts"]
                for target, field in [
                    ("phase_counts", "phases"),
                    ("teacher_action_counts", "teacher_action_types"),
                ]:
                    for key, value in result[field].items():
                        stats[target][key] = stats[target].get(key, 0) + value
                write(out / "status.json", {**stats, "stage": "collecting"})
                print(
                    json.dumps({key: value for key, value in stats.items() if key != "files"}),
                    flush=True,
                )
        write(out / "status.json", {**stats, "stage": "complete", "finished": time.time()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--hands", type=int, default=64)
    parser.add_argument("--start", type=int, default=2026150000)
    parser.add_argument("--rate", type=float, default=0.08)
    parser.add_argument("--worlds", type=int, default=4)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--history", type=int, default=128)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    main(
        (ROOT / args.out).resolve(),
        args.hands,
        args.start,
        args.rate,
        args.worlds,
        args.limit,
        args.history,
        args.workers,
    )
