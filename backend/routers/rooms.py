from __future__ import annotations

import secrets
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.params import Depends
from pydantic import BaseModel, Field

from backend.deps import OptionalUserDep, SessionDep
from backend.models import Room as RoomRow
from backend.models import User, new_id
from backend.security import create_ws_token
from backend.ws.hub import Room, RoomConfig, RoomManager

router = APIRouter(prefix="/rooms", tags=["rooms"])


def get_manager(request: Request) -> RoomManager:
    manager: RoomManager = request.app.state.rooms
    return manager


ManagerDep = Annotated[RoomManager, Depends(get_manager)]


def _no_bots() -> list[int | None]:
    return [None, None, None, None]


class ConfigIn(BaseModel):
    time_limit: float | None = Field(30, description="seconds per action; null = unlimited")
    rounds: int = Field(1, ge=1, le=4)
    base_points: int = Field(100, ge=0)
    tai_points: int = Field(50, ge=0)
    tai_cap: int | None = Field(None, ge=1)
    bot_levels: list[int | None] = Field(default_factory=lambda: _no_bots())
    bot_delay: float = Field(0.6, ge=0, le=5)
    next_hand_delay: float = Field(4.0, ge=0, le=30)
    quick_wait: float = Field(30.0, ge=0, le=120)
    public: bool = False
    tutor: bool = False

    def to_config(self) -> RoomConfig:
        if len(self.bot_levels) != 4 or any(
            lvl is not None and not 1 <= lvl <= 5 for lvl in self.bot_levels
        ):
            raise HTTPException(422, "bot_levels must have 4 entries of null or 1-5")
        if self.time_limit is not None and self.time_limit < 1:
            raise HTTPException(422, "invalid time_limit")
        return RoomConfig(**self.model_dump())


class CreateIn(BaseModel):
    type: Literal["PRIVATE", "QUICK", "PRACTICE"] = "PRIVATE"
    config: ConfigIn = Field(default_factory=lambda: ConfigIn())


class JoinIn(BaseModel):
    seat: int | None = Field(None, ge=0, le=3)
    name: str | None = Field(None, max_length=30)


class JoinOut(BaseModel):
    seat: int
    ws_token: str
    room: dict[str, Any]


def _display_name(user: User | None, name: str | None) -> str:
    if user is not None:
        return user.username
    return name or f"訪客{secrets.randbelow(10000):04d}"


def _room_or_404(manager: RoomManager, room_id: str) -> Room:
    room = manager.get(room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room not found")
    return room


@router.post("/quick/join", response_model=JoinOut)
async def quick_join(body: JoinIn, user: OptionalUserDep, manager: ManagerDep) -> JoinOut:
    """Quick match: join a waiting room or open one; bots fill after `quick_wait` seconds."""
    room = manager.find_quick()
    created = room is None
    if room is None:
        room = manager.create(new_id(), "QUICK", RoomConfig(), None)
    out = _join(room, user, JoinIn(seat=None, name=body.name))
    if created:
        await manager.schedule_quick_start(room)
    elif all(s is not None for s in room.seats):
        await room.start()
    return out


@router.post("", status_code=status.HTTP_201_CREATED)
def create_room(body: CreateIn, db: SessionDep, user: OptionalUserDep,
                manager: ManagerDep) -> dict[str, Any]:
    cfg = body.config.to_config()
    room_id = new_id()
    room = manager.create(room_id, body.type, cfg, user.id if user else None)
    db.add(RoomRow(id=room_id, code=room.code, type=body.type,
                   config=body.config.model_dump(), created_by=user.id if user else None))
    db.commit()
    return {"room_id": room_id, "code": room.code, "room": room.public()}


@router.get("/{code}")
def get_room(code: str, manager: ManagerDep) -> dict[str, Any]:
    room = manager.get_by_code(code) or manager.get(code)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room not found")
    return room.public()


def _join(room: Room, user: User | None, body: JoinIn) -> JoinOut:
    name = _display_name(user, body.name)
    try:
        seat = room.join(user.id if user else None, name, body.seat)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    token = create_ws_token(room.id, seat, user.id if user else None, name)
    return JoinOut(seat=seat, ws_token=token, room=room.public())


@router.post("/{room_id}/join", response_model=JoinOut)
def join_room(room_id: str, body: JoinIn, user: OptionalUserDep,
              manager: ManagerDep) -> JoinOut:
    return _join(_room_or_404(manager, room_id), user, body)


@router.post("/{room_id}/start")
async def start_room(room_id: str, user: OptionalUserDep, manager: ManagerDep
                     ) -> dict[str, Any]:
    room = _room_or_404(manager, room_id)
    if room.host_id is not None and (user is None or user.id != room.host_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only the host can start")
    try:
        await room.start()
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return room.public()
