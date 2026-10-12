"""Training metrics: JSONL (read by the lab dashboard) plus optional TensorBoard/WandB."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

RUNS_DIR = Path(os.environ.get("MAIJONG_RUNS_DIR", "runs"))


class MetricsLogger:
    def __init__(self, run: str, config: dict[str, Any] | None = None) -> None:
        self.dir = RUNS_DIR / run
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "metrics.jsonl"
        (self.dir / "config.json").write_text(json.dumps(config or {}, indent=2))
        self._tb: Any = None
        self._wandb: Any = None
        try:
            from torch.utils.tensorboard import SummaryWriter

            self._tb = SummaryWriter(str(self.dir / "tb"))
        except Exception:  # tensorboard not installed
            self._tb = None
        if os.environ.get("WANDB_PROJECT"):
            try:
                import wandb

                self._wandb = wandb.init(project=os.environ["WANDB_PROJECT"], name=run,
                                         config=config or {})
            except Exception:
                self._wandb = None

    def log(self, step: int, **values: float) -> None:
        rec = {"step": step, "time": time.time(), **values}
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        if self._tb is not None:
            for k, v in values.items():
                self._tb.add_scalar(k, v, step)
        if self._wandb is not None:
            self._wandb.log(values, step=step)

    def close(self) -> None:
        if self._tb is not None:
            self._tb.close()
        if self._wandb is not None:
            self._wandb.finish()


def read_metrics(run: str, since: int | None = None) -> list[dict[str, Any]]:
    """Metric records of a run; with `since`, only those with step > since."""
    path = RUNS_DIR / run / "metrics.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:  # a line being written right now
            continue
        if since is None or rec.get("step", 0) > since:
            out.append(rec)
    return out


def list_runs() -> list[dict[str, Any]]:
    """Every run directory (lab jobs and command-line training alike), newest first."""
    if not RUNS_DIR.exists():
        return []
    rows = []
    for d in RUNS_DIR.iterdir():
        metrics = d / "metrics.jsonl"
        if not d.is_dir() or not metrics.exists():
            continue
        try:
            config = json.loads((d / "config.json").read_text())
        except (OSError, json.JSONDecodeError):
            config = {}
        series = read_metrics(d.name)
        last: dict[str, Any] = {}
        for rec in series:
            last.update(rec)
        rows.append({
            "name": d.name, "kind": str(config.get("kind", "")),
            "updated_at": metrics.stat().st_mtime, "points": len(series),
            "last_step": last.get("step"), "eval_win_rate": last.get("eval_win_rate"),
        })
    return sorted(rows, key=lambda r: r["updated_at"], reverse=True)
