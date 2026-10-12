"""Celery task definitions (optional; used when CELERY_BROKER_URL is set).

Start a worker with:  celery -A backend.tasks.training_tasks worker -l info
Rated arena matches (P10-1) on a schedule:
    ARENA_INTERVAL=60 celery -A backend.tasks.training_tasks worker --beat -l info
With --beat, hands not yet replay-verified are swept every REPLAY_VERIFY_INTERVAL seconds
(default 3600; 0 turns it off).
"""

from __future__ import annotations

import os
from typing import Any

try:
    from celery import Celery
except ImportError:  # celery is optional for local development
    Celery = None

app: Any = None
if Celery is not None and os.environ.get("CELERY_BROKER_URL"):
    app = Celery("maijong", broker=os.environ["CELERY_BROKER_URL"],
                 backend=os.environ.get("CELERY_RESULT_BACKEND"))

    @app.task(name="maijong.simulate")
    def simulate(job_id: str, specs: list[str], hands: int, seed: int) -> None:
        from backend.tasks.runner import _simulation

        _simulation(job_id, specs, hands, seed)

    @app.task(name="maijong.train")
    def train(job_id: str, kind: str, config: dict[str, Any]) -> None:
        from backend.tasks.runner import start_training

        start_training(job_id, kind, config)

    @app.task(name="maijong.arena_match")
    def arena_match() -> dict[str, Any] | None:
        """Play one rated match between eligible agents (see backend.arena)."""
        return run_one_arena_match()

    @app.task(name="maijong.verify_replays")
    def verify_replays() -> dict[str, int]:
        """Re-run hands that were never verified (SPEC 11, see backend.replay_check)."""
        return run_replay_sweep()

    _schedule: dict[str, Any] = {}
    _interval = float(os.environ.get("ARENA_INTERVAL", "0"))
    if _interval > 0:
        _schedule["arena-match"] = {"task": "maijong.arena_match", "schedule": _interval}
    _verify_every = float(os.environ.get("REPLAY_VERIFY_INTERVAL", "3600"))
    if _verify_every > 0:
        _schedule["verify-replays"] = {"task": "maijong.verify_replays", "schedule": _verify_every}
    app.conf.beat_schedule = _schedule


def run_one_arena_match() -> dict[str, Any] | None:
    from backend.arena import run_arena_match
    from backend.db import session_factory

    with session_factory()() as db:
        result: dict[str, Any] | None = run_arena_match(db)
        return result


def run_replay_sweep() -> dict[str, int]:
    from backend.db import session_factory
    from backend.replay_check import verify_pending

    with session_factory()() as db:
        return verify_pending(db)
