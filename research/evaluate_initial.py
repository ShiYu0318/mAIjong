# Direct-script entry points bootstrap the repository path before local imports.
# ruff: noqa: E402
"""Independent exploratory evaluation of the first PPO control checkpoint."""

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch

from ai.training.duplicate import paired


def main():
    torch.set_num_threads(2)
    output = ROOT / "runs/research-20261101/control-01"
    candidate = "ppo:checkpoints/research-20261101-control-01.pt"
    for name, baseline, seed in [
        ("holdout_vs_cem", "tuned:checkpoints/rule_cem_v1.json", 2026112000),
        ("holdout_vs_initial", "ppo:checkpoints/ppo_v7.pt", 2026113000),
    ]:
        result = paired(candidate, baseline, hands=1024, opponent="rule", workers=2, seed=seed)
        record = {
            "candidate": candidate,
            "baseline": baseline,
            "opponent": "rule",
            "seed": seed,
            "result": asdict(result),
            "candidate_sha256": hashlib.sha256(
                (ROOT / candidate.split(":", 1)[1]).read_bytes()
            ).hexdigest(),
            "note": (
                'Exploratory holdout, never reuse as final confirmation after '
                'selecting further candidates.'
            ),
        }
        (output / (name + ".json")).write_text(json.dumps(record, indent=2))
        print(name, result.line(candidate, baseline), flush=True)


if __name__ == "__main__":
    main()
