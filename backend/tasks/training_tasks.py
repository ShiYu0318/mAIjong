"""Celery task definitions (optional; used when CELERY_BROKER_URL is set).

Start a worker with:  celery -A backend.tasks.training_tasks worker -l info
Rated arena matches (P10-1) on a schedule:
    ARENA_INTERVAL=60 celery -A backend.tasks.training_tasks worker --beat -l info
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

    _interval = float(os.environ.get("ARENA_INTERVAL", "0"))
    if _interval > 0:
        app.conf.beat_schedule = {
            "arena-match": {"task": "maijong.arena_match", "schedule": _interval},
        }


def run_one_arena_match() -> dict[str, Any] | None:
    from backend.arena import run_arena_match
    from backend.db import session_factory

    with session_factory()() as db:
        result: dict[str, Any] | None = run_arena_match(db)
        return result
