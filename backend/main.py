"""FastAPI application factory.

Run locally:  uv run uvicorn backend.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db import init_db, session_factory
from backend.persistence import save_hand
from backend.routers import auth, games, lab, rooms, tutor
from backend.ws import game_ws
from backend.ws.hub import Room, RoomManager
from engine.game import GameState

API_PREFIX = "/api/v1"


def _save_hand(room: Room, g: GameState, hand_index: int, seats: list[Any],
               decisions: dict[int, dict[str, Any]], actions: list[list[int]]) -> None:
    with session_factory()() as db:
        save_hand(db, g, room_id=room.id, hand_index=hand_index, seats=seats,
                  decisions=decisions, actions=actions, is_public=room.config.public)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    app.state.rooms = RoomManager(save_hook=_save_hand)
    yield
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
    app.include_router(game_ws.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
