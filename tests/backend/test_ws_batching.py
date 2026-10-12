"""WebSocket message batching (SPEC P11-7)."""

from __future__ import annotations

import asyncio
from typing import Any

from backend.ws.batching import BatchingSocket, coalesce
from tests.backend.test_rooms_ws import create


def test_coalesce_keeps_only_the_newest_state_update():
    msgs = [{"type": "STATE_UPDATE", "payload": {"v": 1}}, {"type": "PLAYER_ACTION"},
            {"type": "STATE_UPDATE", "payload": {"v": 2}}, {"type": "ACTION_REQUEST"}]
    out = coalesce(msgs)
    assert [m["type"] for m in out] == ["PLAYER_ACTION", "STATE_UPDATE", "ACTION_REQUEST"]
    assert out[1]["payload"]["v"] == 2


def test_batching_socket_writes_one_frame_per_burst():
    class Fake:
        def __init__(self) -> None:
            self.frames: list[Any] = []

        async def send_json(self, data: Any) -> None:
            self.frames.append(data)

    async def run() -> Fake:
        fake = Fake()
        sock = BatchingSocket(fake)
        for i in range(3):
            await sock.send_json({"type": "PLAYER_ACTION", "payload": {"i": i}})
        await sock.drain()
        await sock.send_json({"type": "PONG", "payload": {}})
        await sock.drain()
        return fake

    fake = asyncio.run(run())
    assert len(fake.frames) == 2
    assert fake.frames[0]["type"] == "BATCH" and len(fake.frames[0]["payload"]["messages"]) == 3
    assert fake.frames[1] == {"type": "PONG", "payload": {}}


def unpack(frame: dict[str, Any]) -> list[dict[str, Any]]:
    return frame["payload"]["messages"] if frame["type"] == "BATCH" else [frame]


def test_batched_client_plays_a_whole_match(client):
    room = create(client, [None, 3, 3, 3])
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={"name": "批次"}).json()
    seat = j["seat"]
    frames = messages = 0
    batched = False
    url = f"/ws/game/{room['room_id']}?token={j['ws_token']}&batch=1"
    with client.websocket_connect(url) as ws:
        client.post(f"/api/v1/rooms/{room['room_id']}/start")
        done = False
        while not done:
            frame = ws.receive_json()
            frames += 1
            batch = unpack(frame)
            batched = batched or frame["type"] == "BATCH"
            messages += len(batch)
            for msg in batch:
                if msg["type"] == "GAME_END":
                    done = True
                elif msg["type"] == "ACTION_REQUEST" and msg["payload"]["player"] == seat:
                    legal = msg["payload"]["legal_actions"]
                    pick = next((a for a in legal if a["action_type"] == "PASS"), legal[0])
                    ws.send_json({"type": "ACTION", "payload": pick})
    assert batched and frames < messages
