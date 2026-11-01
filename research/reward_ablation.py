# Direct-script entry points bootstrap the repository path before local imports.
# ruff: noqa: E402
"""Matched-budget, three-seed reward ablation. Artifacts remain local."""

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

from ai.training.ppo_trainer import PPOConfig, train_ppo

OUT = ROOT / "runs/research-20261101/reward-ablation-01"


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2))


def main():
    torch.set_num_threads(2)
    OUT.mkdir(parents=True, exist_ok=False)
    initial = ROOT / "checkpoints/ppo_v7.pt"
    files = ["ai/reward.py", "ai/training/ppo_trainer.py", "research/reward_ablation.py"]
    write(
        "manifest.json",
        {
            "commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_sha256": {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files
            },
            "initial_sha256": hashlib.sha256(initial.read_bytes()).hexdigest(),
            "seeds": [20261102, 20261103, 20261104],
            "rewards": ["potential", "score", "discounted"],
            "note": (
                'Short screening; selection eval is not final confirmation. No '
                'automatic promotion.'
            ),
        },
    )
    for seed in [20261102, 20261103, 20261104]:
        for reward in ["potential", "score", "discounted"]:
            name = f"research-reward01-{reward}-{seed}"
            cfg = PPOConfig(
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
                reward=reward,
                device="cpu",
            )
            checkpoint = ROOT / "checkpoints" / (name + ".pt")
            write("status.json", {"stage": "training", "run": name, "time": time.time()})
            write(name + "-config.json", asdict(cfg))
            best = train_ppo(cfg, checkpoint, initial, name)
            write(
                name + "-result.json",
                {
                    "selection_eval": best,
                    "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                },
            )
            print(name, best, flush=True)
    write("status.json", {"stage": "complete", "time": time.time()})


if __name__ == "__main__":
    main()
