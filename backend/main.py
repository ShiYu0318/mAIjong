"""FastAPI application factory.

Run locally:  uv run uvicorn backend.main:app --reload
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import Settings, get_settings
from backend.db import init_db, session_factory
from backend.models import Room as RoomRow
from backend.persistence import save_hand
from backend.replay_check import verify_game
from backend.routers import (
    agents,
    auth,
    competition,
    games,
    lab,
    practice,
    profile,
    rooms,
    tutor,
)
from backend.security_middleware import SecurityMiddleware
from backend.ws import game_ws
from backend.ws.hub import Room, RoomManager
from backend.ws.store import store_from_settings
from engine.game import GameState

API_PREFIX = "/api/v1"


def _save_hand(room: Room, g: GameState, hand_index: int, seats: list[Any],
               decisions: dict[int, dict[str, Any]], actions: list[list[int]]) -> None:
    with session_factory()() as db:
        if db.get(RoomRow, room.id) is None:  # quick-match / arena rooms live only in memory
            db.add(RoomRow(id=room.id, code=room.code, type=room.kind,
                           config=room.public()["config"], created_by=room.host_id))
            db.flush()
        game = save_hand(db, g, room_id=room.id, hand_index=hand_index, seats=seats,
                         decisions=decisions, actions=actions, is_public=room.config.public,
                         scenario=room.scenario)
        # already off the event loop (asyncio.to_thread): re-run the hand right away
        verify_game(db, game)


def _progress(room: Room, g: GameState, final_scores: list[int] | None
              ) -> dict[int, list[dict[str, Any]]]:
    """Level/mission/achievement updates for every seated account (docs design §8)."""
    from backend import progression
    from backend.models import User
    from engine.match import ranks

    out: dict[int, list[dict[str, Any]]] = {}
    if g.result is None or room.scenario is not None:
        return out
    order = ranks(final_scores) if final_scores is not None else None
    with session_factory()() as db:
        for st in room.seats:
            if st is None or st.user_id is None or st.is_bot:
                continue
            user = db.get(User, st.user_id)
            if user is None:
                continue
            events = progression.record_hand(db, user, st.index, g.result,
                                             bool(g.declared_ting[st.index]))
            if order is not None:
                events += progression.record_match(db, user, order[st.index])
            p = progression.get_progress(db, user)
            out[st.index] = [*events, {"type": "STATE", "level": p.level, "xp": p.xp,
                                       "xp_next": progression.xp_for_next(p.level),
                                       "coins": p.coins}]
        db.commit()
    return out


async def _arena_loop(interval: float) -> None:
    """Play a rated arena match every `interval` seconds (P10-1). With Celery configured,
    the beat schedule in backend.tasks.training_tasks does this instead."""
    from backend.tasks.training_tasks import run_one_arena_match

    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(run_one_arena_match)
        except Exception:
            logging.getLogger("maijong.arena").exception("arena match failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    from backend.routers.competition import current_season

    with session_factory()() as db:
        current_season(db)  # rankings count from the start of the active season
    app.state.rooms = RoomManager(save_hook=_save_hand, store=store_from_settings(),
                                  progress_hook=_progress)
    restored = await app.state.rooms.restore()
    if restored:
        logging.getLogger("maijong").info("restored %d rooms from Redis", restored)
    interval = float(os.environ.get("ARENA_INTERVAL", "0"))
    in_process = interval > 0 and not os.environ.get("CELERY_BROKER_URL")
    arena = asyncio.create_task(_arena_loop(interval)) if in_process else None
    yield
    if arena is not None:
        arena.cancel()
    await app.state.rooms.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.secret_key == Settings().secret_key and not settings.debug and \
            settings.database_url.startswith("postgresql"):
        logging.getLogger("maijong").warning("SECRET_KEY is the development default; set one")
    app = FastAPI(title="mAIjong", version="0.1.0", lifespan=lifespan)
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(rooms.router, prefix=API_PREFIX)
    app.include_router(tutor.router, prefix=API_PREFIX)
    app.include_router(games.router, prefix=API_PREFIX)
    app.include_router(lab.router, prefix=API_PREFIX)
    app.include_router(agents.router, prefix=API_PREFIX)
    app.include_router(competition.router, prefix=API_PREFIX)
    app.include_router(practice.router, prefix=API_PREFIX)
    app.include_router(profile.router, prefix=API_PREFIX)
    app.include_router(game_ws.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
