# Direct-script entry points bootstrap the repository path before local imports.
# ruff: noqa: E402
"""Resumable, preregistered block evaluation of completed reward-ablation models."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch

from ai.training.block_evaluate import bootstrap_interval, play_block

OUT = ROOT / "runs/research-20261101/reward-ablation-eval-01"
TRAIN = ROOT / "runs/research-20261101/reward-ablation-01"
BLOCKS = 128
POOLS = ["rule", "tuned:checkpoints/rule_cem_v1.json"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=True)
    plan = {
        "blocks": BLOCKS,
        "pools": POOLS,
        "baseline": "ppo:checkpoints/ppo_v7.pt",
        "seeds": [20261102, 20261103, 20261104],
        "rewards": ["potential", "score", "discounted"],
        "deal_seed_start": 2026114000,
        "baseline_sha256": sha(ROOT / "checkpoints/ppo_v7.pt"),
        "cem_sha256": sha(ROOT / "checkpoints/rule_cem_v1.json"),
        "evaluator_sha256": sha(ROOT / "ai/training/block_evaluate.py"),
    }
    manifest = OUT / "manifest.json"
    if manifest.exists():
        assert json.loads(manifest.read_text()) == plan, "Evaluation plan changed"
    else:
        manifest.write_text(json.dumps(plan, indent=2))
    for seed in plan["seeds"]:
        for reward in plan["rewards"]:
            name = f"research-reward01-{reward}-{seed}"
            training_result = TRAIN / (name + "-result.json")
            if not training_result.exists():
                continue  # Only evaluate final selected, no-longer-mutating checkpoints.
            checkpoint = ROOT / "checkpoints" / (name + ".pt")
            expected_hash = json.loads(training_result.read_text())["checkpoint_sha256"]
            assert sha(checkpoint) == expected_hash
            for pool_id, opponent in enumerate(POOLS):
                rows_file = OUT / f"{name}-pool{pool_id}.jsonl"
                rows = (
                    [json.loads(x) for x in rows_file.read_text().splitlines()]
                    if rows_file.exists()
                    else []
                )
                cache = {}
                for k in range(BLOCKS):
                    deal_seed = plan["deal_seed_start"] + pool_id * 100000 + k
                    if k < len(rows):
                        assert rows[k]["seed"] == deal_seed
                        assert rows[k]["checkpoint_sha256"] == expected_hash
                        continue
                    row = play_block(
                        "ppo:" + str(checkpoint), plan["baseline"], opponent, deal_seed, cache=cache
                    )
                    row["checkpoint_sha256"] = expected_hash
                    with rows_file.open("a") as stream:
                        stream.write(json.dumps(row) + "\n")
                    rows.append(row)
                means = [r["mean_difference"] for r in rows]
                summary = {
                    "candidate": name,
                    "opponent": opponent,
                    "blocks": len(rows),
                    "mean_difference": sum(means) / len(means),
                    "bootstrap_ci95": bootstrap_interval(means, seed=823),
                    "checkpoint_sha256": expected_hash,
                }
                (OUT / f"{name}-pool{pool_id}-summary.json").write_text(
                    json.dumps(summary, indent=2)
                )
                print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
