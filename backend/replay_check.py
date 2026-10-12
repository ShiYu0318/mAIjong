"""Replay verification (SPEC 11): every finished hand is re-run from its stored seed and
action log, and must reproduce the saved events and result.

New hands are checked as they are saved; `python -m backend.replay_check` (or the hourly
Celery beat task) sweeps any hand that has not been checked yet.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Game
from backend.persistence import read_replay
from backend.replay import ReplayError, verify_records

log = logging.getLogger("maijong.replay_check")


def verify_game(db: Session, game: Game) -> bool:
    """Re-run one hand and store the outcome on the row."""
    try:
        verify_records(read_replay(game.id))
        ok = True
    except (ReplayError, KeyError, ValueError, OSError) as exc:
        log.error("replay verification failed for %s: %s", game.id, exc)
        ok = False
    game.replay_verified = ok
    db.commit()
    return ok


def verify_pending(db: Session, limit: int = 500) -> dict[str, int]:
    """Check up to `limit` hands that were never verified; returns counts."""
    games = db.scalars(select(Game).where(Game.replay_verified.is_(None))
                       .order_by(Game.created_at).limit(limit)).all()
    passed = sum(verify_game(db, g) for g in games)
    return {"checked": len(games), "passed": passed, "failed": len(games) - passed}


def main() -> int:
    from backend.db import init_db, session_factory

    logging.basicConfig(level=logging.INFO)
    init_db()
    total = {"checked": 0, "passed": 0, "failed": 0}
    with session_factory()() as db:
        while True:
            batch = verify_pending(db)
            for k, v in batch.items():
                total[k] += v
            if batch["checked"] == 0:
                break
    print(f"checked {total['checked']} hands: {total['passed']} ok, {total['failed']} failed")
    return 1 if total["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
