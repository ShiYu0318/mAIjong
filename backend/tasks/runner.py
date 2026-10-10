"""Background jobs for the lab (SPEC P8-1).

Jobs are rows in training_jobs. Simulations run in a thread pool inside the API
process; training runs as a separate Python process writing metrics to runs/<job id>/.
With CELERY_BROKER_URL set, backend/tasks/training_tasks.py offers the same work as
Celery tasks for multi-machine deployments.
"""

from __future__ import annotations

import logging
import math
import os
import signal
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from backend.db import session_factory
from backend.models import TrainingJob, now

log = logging.getLogger("maijong.jobs")
_pool = ThreadPoolExecutor(max_workers=int(os.environ.get("LAB_WORKERS", "2")))
_procs: dict[str, subprocess.Popen[bytes]] = {}
_lock = threading.Lock()
ROOT = Path(__file__).resolve().parents[2]


def _update(job_id: str, **fields: Any) -> None:
    with session_factory()() as db:
        job = db.get(TrainingJob, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        db.commit()


def binomial_p_value(successes: int, n: int, p: float) -> float:
    """Two-sided normal-approximation p-value for a binomial proportion."""
    if n == 0:
        return 1.0
    sd = math.sqrt(n * p * (1 - p))
    if sd == 0:
        return 1.0
    z = abs(successes - n * p) / sd
    return math.erfc(z / math.sqrt(2))


def _simulation(job_id: str, specs: list[str], hands: int, seed: int) -> None:
    from ai.simulate import run_batch

    _update(job_id, status="RUNNING", metrics={"progress": 0.0})
    try:
        def progress(done: int) -> None:
            _update(job_id, metrics={"progress": done / hands, "done": done})

        res = run_batch(specs, hands, seed, workers=max(1, (os.cpu_count() or 2) - 2),
                        progress=progress)
        summary = res.summary()
        # per distinct agent: pooled stats + significance of the win share
        pooled: dict[str, dict[str, float]] = {}
        decisive = summary["hands"] * (1 - summary["draw_rate"])
        for seat in summary["seats"]:
            p = pooled.setdefault(seat["agent"], {"seats": 0, "wins": 0.0, "deal_ins": 0.0,
                                                  "score": 0.0, "tai": 0.0, "self_draws": 0.0})
            n = seat["hands"]
            p["seats"] += 1
            p["wins"] += seat["win_rate"] * n
            p["deal_ins"] += seat["deal_in_rate"] * n
            p["self_draws"] += seat["self_draw_rate"] * n
            p["score"] += seat["avg_score"] * n
            p["tai"] += seat["avg_tai_on_win"] * seat["win_rate"] * n
        agents = []
        for name, p in pooled.items():
            share = p["seats"] / 4
            n_hands = summary["hands"] * p["seats"]
            agents.append({
                "agent": name,
                "win_rate": p["wins"] / n_hands,
                "self_draw_rate": p["self_draws"] / n_hands,
                "deal_in_rate": p["deal_ins"] / n_hands,
                "avg_score": p["score"] / n_hands,
                "avg_tai_on_win": p["tai"] / max(1, p["wins"]),
                "win_share": p["wins"] / max(1, decisive),
                "p_value": binomial_p_value(round(p["wins"]), round(decisive), share),
            })
        _update(job_id, status="DONE", finished_at=now(),
                metrics={"progress": 1.0, "summary": summary, "agents": agents})
    except Exception as e:  # report failures on the job
        log.exception("simulation %s failed", job_id)
        _update(job_id, status="FAILED", finished_at=now(), metrics={"error": str(e)})


def submit_simulation(job_id: str, specs: list[str], hands: int, seed: int) -> None:
    _pool.submit(_simulation, job_id, specs, hands, seed)


TRAIN_MODULES = {"ppo": "ai.training.ppo_trainer", "dqn": "ai.training.dqn_trainer",
                 "bc": "ai.training.bc_trainer"}


def _train_args(job_id: str, kind: str, config: dict[str, Any]) -> list[str]:
    args = [sys.executable, "-m", TRAIN_MODULES[kind], "--run", job_id]
    ckpt = ROOT / "checkpoints"
    if kind == "ppo":
        args += ["--updates", str(int(config.get("updates", 100))),
                 "--envs", str(int(config.get("envs", 8))),
                 "--out", str(ckpt / f"ppo_{job_id}.pt")]
        if config.get("init"):
            args += ["--init", str(config["init"])]
    elif kind == "dqn":
        args += ["--steps", str(int(config.get("steps", 100_000))),
                 "--out", str(ckpt / f"dqn_{job_id}.pt")]
    else:
        args += ["--data", str(config["data"]), "--out", str(ckpt / f"bc_{job_id}.pt")]
    return args


def _watch(job_id: str, proc: subprocess.Popen[bytes]) -> None:
    code = proc.wait()
    with _lock:
        _procs.pop(job_id, None)
    with session_factory()() as db:
        job = db.get(TrainingJob, job_id)
        if job is None or job.status == "STOPPED":
            return
        job.status = "DONE" if code == 0 else "FAILED"
        job.finished_at = now()
        db.commit()


def start_training(job_id: str, kind: str, config: dict[str, Any]) -> None:
    if kind not in TRAIN_MODULES:
        raise ValueError(f"unknown training kind {kind}")
    env = {**os.environ, "MAIJONG_RUNS_DIR": str(ROOT / "runs")}
    log_path = ROOT / "runs" / job_id / "stdout.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as out:
        proc = subprocess.Popen(_train_args(job_id, kind, config), cwd=ROOT, env=env,
                                stdout=out, stderr=subprocess.STDOUT)
    with _lock:
        _procs[job_id] = proc
    _update(job_id, status="RUNNING", finished_at=None)
    threading.Thread(target=_watch, args=(job_id, proc), daemon=True).start()


def stop_training(job_id: str) -> bool:
    with _lock:
        proc = _procs.get(job_id)
    _update(job_id, status="STOPPED", finished_at=now())
    if proc is None:
        return False
    proc.send_signal(signal.SIGTERM)
    return True


def checkpoint_for(job_id: str, kind: str) -> Path:
    return ROOT / "checkpoints" / f"{kind}_{job_id}.pt"
