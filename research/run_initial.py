# Direct-script entry points bootstrap the repository path before local imports.
# ruff: noqa: E402
"""Initial reproducible audit and PPO control experiment; never promotes models."""

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

from ai.training.duplicate import paired
from ai.training.ppo_trainer import PPOConfig, train_ppo

OUT = ROOT / "runs/research-20261101/control-01"
OUT.mkdir(parents=True, exist_ok=True)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    torch.set_num_threads(2)
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
        seed=20261101,
        reward="potential",
        device="cpu",
    )
    manifest = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "started": time.time(),
        "config": asdict(cfg),
        "initial_sha256": sha("checkpoints/ppo_v7.pt"),
        "cem_sha256": sha("checkpoints/rule_cem_v1.json"),
        "baseline_seed": 2026110100,
        "baseline_deals": 512,
        "note": (
            'Control uses legacy potential reward. Training eval seeds are '
            'selection data, not final holdout.'
        ),
    }
    write("manifest.json", manifest)
    write("status.json", {"stage": "baseline", "time": time.time()})
    result = paired(
        "ppo:checkpoints/ppo_v7.pt",
        "tuned:checkpoints/rule_cem_v1.json",
        hands=512,
        opponent="rule",
        workers=2,
        seed=2026110100,
    )
    write("baseline.json", asdict(result))
    print("BASELINE", result.line("ppo_v7", "cem_v1"), flush=True)
    write("status.json", {"stage": "training", "time": time.time()})
    out = ROOT / "checkpoints/research-20261101-control-01.pt"
    best = train_ppo(cfg, out, ROOT / "checkpoints/ppo_v7.pt", "research-20261101-control-01")
    write(
        "training_result.json",
        {
            "best_selection_eval": best,
            "checkpoint_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        },
    )
    write("status.json", {"stage": "complete", "time": time.time()})
    print("TRAINING_COMPLETE", best, flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        write("status.json", {"stage": "failed", "error": repr(exc), "time": time.time()})
        raise
