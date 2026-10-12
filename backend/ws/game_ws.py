"""WebSocket endpoint: ws://host/ws/game/{room_id}?token={ws_token}[&batch=1]

Without a token the connection joins as a spectator (no concealed tiles).
"""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.security import TokenError, decode_token
from backend.security_middleware import TokenBucket, _limit
from backend.ws.batching import BatchingSocket
from backend.ws.hub import RoomManager

router = APIRouter()


@router.websocket("/ws/game/{room_id}")
async def game_socket(ws: WebSocket, room_id: str, token: str | None = None,
                      batch: int = 0) -> None:
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
    sock: Any = BatchingSocket(ws) if batch else ws
    await room.connect(seat, sock)
    bucket = TokenBucket(_limit("RATE_LIMIT_WS_PER_SEC", "20"), 1)  # per socket
    try:
        while True:
            msg: Any = await ws.receive_json()
            if seat is None or not isinstance(msg, dict):
                continue
            if not bucket.allow("ws"):
                await sock.send_json({"type": "ERROR", "payload": {
                    "code": "RATE_LIMIT", "message": "訊息太頻繁，請稍候"}})
                continue
            await room.handle(seat, msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        with contextlib.suppress(Exception):
            await room.disconnect(seat, sock)
