"""WebSocket endpoint: ws://host/ws/game/{room_id}?token={ws_token}

Without a token the connection joins as a spectator (no concealed tiles).
"""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.security import TokenError, decode_token
from backend.ws.hub import RoomManager

router = APIRouter()


@router.websocket("/ws/game/{room_id}")
async def game_socket(ws: WebSocket, room_id: str, token: str | None = None) -> None:
    manager: RoomManager = ws.app.state.rooms
    room = manager.get(room_id)
    seat: int | None = None
    if token:
        try:
            claims = decode_token(token, "ws")
        except TokenError:
            await ws.close(code=4401)
            return
        if claims.get("room") != room_id:
            await ws.close(code=4403)
            return
        seat = int(claims["seat"])
    if room is None:
        await ws.close(code=4404)
        return
    await ws.accept()
    await room.connect(seat, ws)
    try:
        while True:
            msg: Any = await ws.receive_json()
            if seat is None or not isinstance(msg, dict):
                continue
            await room.handle(seat, msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        with contextlib.suppress(Exception):
            await room.disconnect(seat, ws)
