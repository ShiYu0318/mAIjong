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

from backend.config import get_settings
from backend.db import init_db, session_factory
from backend.models import Room as RoomRow
from backend.persistence import save_hand
from backend.routers import agents, auth, competition, games, lab, rooms, tutor
from backend.ws import game_ws
from backend.ws.hub import Room, RoomManager
from engine.game import GameState

API_PREFIX = "/api/v1"


def _save_hand(room: Room, g: GameState, hand_index: int, seats: list[Any],
               decisions: dict[int, dict[str, Any]], actions: list[list[int]]) -> None:
    with session_factory()() as db:
        if db.get(RoomRow, room.id) is None:  # quick-match / arena rooms live only in memory
            db.add(RoomRow(id=room.id, code=room.code, type=room.kind,
                           config=room.public()["config"], created_by=room.host_id))
            db.flush()
        save_hand(db, g, room_id=room.id, hand_index=hand_index, seats=seats,
                  decisions=decisions, actions=actions, is_public=room.config.public)


async def _arena_loop(interval: float) -> None:
    """Play a rated arena match every `interval` seconds (P10-1)."""
    from backend.arena import run_arena_match

    def one() -> None:
        with session_factory()() as db:
            run_arena_match(db)

    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(one)
        except Exception:
            logging.getLogger("maijong.arena").exception("arena match failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    from backend.routers.competition import current_season

    with session_factory()() as db:
        current_season(db)  # rankings count from the start of the active season
    app.state.rooms = RoomManager(save_hook=_save_hand)
    interval = float(os.environ.get("ARENA_INTERVAL", "0"))
    arena = asyncio.create_task(_arena_loop(interval)) if interval > 0 else None
    yield
    if arena is not None:
        arena.cancel()
    await app.state.rooms.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="mAIjong", version="0.1.0", lifespan=lifespan)
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
    app.include_router(game_ws.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
