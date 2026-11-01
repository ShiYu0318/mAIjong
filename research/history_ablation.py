# Direct-script entry points bootstrap the repository path before local imports.
# ruff: noqa: E402
"""Local matched-budget history ablation; never promotes checkpoints automatically."""

import fcntl
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch

from ai.training.block_evaluate import bootstrap_interval, play_block
from ai.training.ppo_trainer import PPOConfig, train_ppo

OUT = ROOT / "runs/research-20261101/history-ablation-01"
SEEDS = [20261105, 20261106, 20261107]
POOLS = ["rule", "tuned:checkpoints/rule_cem_v1.json"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def main():
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "runner.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()


def run():
    initial = ROOT / "checkpoints/ppo_v7.pt"
    sources = sorted(
        [*ROOT.glob("ai/**/*.py"), *ROOT.glob("engine/**/*.py"), Path(__file__).resolve()]
    )
    configs = {}
    for seed in SEEDS:
        for history in [False, True]:
            name = f"research-history01-{int(history)}-{seed}"
            configs[name] = PPOConfig(
                n_envs=4,
                rollout_steps=128,
                updates=24,
                mini_batch=256,
                n_epochs=2,
                lr=3e-5,
                lr_min=1e-5,
                value_warmup=4,
                eval_every=12,
                eval_hands=64,
                snapshot_every=6,
                seed=seed,
                reward="score",
                gamma=1.0,
                device="cpu",
                use_history=history,
                history_length=128,
            )
    plan = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "sources": {str(p.relative_to(ROOT)): sha(p) for p in sources},
        "initial_sha256": sha(initial),
        "cem_sha256": sha(ROOT / "checkpoints/rule_cem_v1.json"),
        "configs": {name: asdict(cfg) for name, cfg in configs.items()},
        "evaluation": {
            "blocks": 128,
            "pools": POOLS,
            "seed_start": 2026118000,
            "bootstrap_seed": 823,
            "comparison": "history versus no-history with same training seed",
        },
        "limitations": [
            "short screening budget",
            "exploratory multiple comparisons",
            "selection remains win-rate first on 64 hands",
            "history is bounded and re-encoded, not persistent rollout memory",
            "equal transitions; history uses more compute",
            "history branch initialization changes the training RNG stream",
        ],
    }
    manifest = OUT / "manifest.json"
    if manifest.exists():
        if json.loads(manifest.read_text()) != plan:
            raise RuntimeError("Source or plan changed; use a new experiment directory")
    else:
        write(manifest, plan)
        for source in sources:
            target = OUT / "source" / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    for name, cfg in configs.items():
        checkpoint = ROOT / "checkpoints" / (name + ".pt")
        result_path = OUT / (name + "-result.json")
        if result_path.exists():
            if sha(checkpoint) != json.loads(result_path.read_text())["checkpoint_sha256"]:
                raise RuntimeError("Completed checkpoint changed")
            continue
        write(OUT / "status.json", {"stage": "training", "run": name, "time": time.time()})
        # An interrupted training run restarts from the same initial model, not partial weights.
        result = train_ppo(cfg, checkpoint, initial, name)
        write(result_path, {"selection_eval": result, "checkpoint_sha256": sha(checkpoint)})
        print(name, result, flush=True)
    for seed in SEEDS:
        paths = [ROOT / "checkpoints" / f"research-history01-{h}-{seed}.pt" for h in [0, 1]]
        hashes = [sha(p) for p in paths]
        for pool_id, opponent in enumerate(POOLS):
            stem = f"paired-{seed}-pool{pool_id}"
            write(OUT / "status.json", {"stage": "evaluating", "run": stem, "time": time.time()})
            rows_path = OUT / (stem + ".jsonl")
            rows = (
                [json.loads(x) for x in rows_path.read_text().splitlines()]
                if rows_path.exists()
                else []
            )
            cache = {}
            for k in range(plan["evaluation"]["blocks"]):
                deal_seed = plan["evaluation"]["seed_start"] + pool_id * 100000 + k
                if k < len(rows):
                    if rows[k]["seed"] != deal_seed or rows[k]["checkpoint_hashes"] != hashes:
                        raise RuntimeError("Saved evaluation row does not match plan")
                    continue
                row = play_block(
                    "ppo:" + str(paths[1]), "ppo:" + str(paths[0]), opponent, deal_seed, cache=cache
                )
                row["checkpoint_hashes"] = hashes
                with rows_path.open("a") as stream:
                    stream.write(json.dumps(row) + "\n")
                rows.append(row)
            means = [r["mean_difference"] for r in rows]
            summary = {
                "seed": seed,
                "opponent": opponent,
                "blocks": len(means),
                "history_minus_control": sum(means) / len(means),
                "bootstrap_ci95": bootstrap_interval(means, seed=823),
                "checkpoint_hashes": hashes,
            }
            write(OUT / (stem + "-summary.json"), summary)
            print(json.dumps(summary), flush=True)
    write(OUT / "status.json", {"stage": "complete", "time": time.time()})


if __name__ == "__main__":
    main()
