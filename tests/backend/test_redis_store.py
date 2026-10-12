"""Room state in Redis (SPEC P2-3): snapshots, restart recovery and spectator relay."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

fakeredis = pytest.importorskip("fakeredis")

from backend.ws.hub import RoomConfig, RoomManager  # noqa: E402
from backend.ws.store import RedisStore  # noqa: E402
from backend.ws.view import masked_state  # noqa: E402
from engine.game import Phase, acting_players, get_legal_actions  # noqa: E402

FAST = dict(time_limit=None, rounds=1, bot_delay=0.0, next_hand_delay=0.0)


def make_store(server: Any, instance: str = "a") -> RedisStore:
    return RedisStore(fakeredis.FakeAsyncRedis(server=server, decode_responses=True), instance)


def test_store_round_trip_and_pubsub():
    server = fakeredis.FakeServer()

    async def run() -> None:
        store = make_store(server)
        await store.save("r1", {"id": "r1", "status": "IN_GAME"})
        owned = await store.load_owned()
        assert [s["id"] for s in owned] == ["r1"] and owned[0]["owner"] == "a"
        assert await make_store(server, "b").load_owned() == []  # other instance owns nothing

        received: list[dict[str, Any]] = []

        async def listen() -> None:
            async for msg in store.subscribe("r1"):
                received.append(msg)
                return

        task = asyncio.create_task(listen())
        await asyncio.sleep(0.05)
        await make_store(server, "b").publish("r1", {"type": "CHAT", "payload": {"m": "hi"}})
        await asyncio.wait_for(task, 2)
        assert received == [{"type": "CHAT", "payload": {"m": "hi"}}]

        await store.delete("r1")
        assert await store.load("r1") is None and await store.load_owned() == []

    asyncio.run(run())


async def _wait_for_human(room: Any, seat: int) -> None:
    for _ in range(500):
        g = room.game
        if g is not None and g.phase is not Phase.ENDED and seat in acting_players(g):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("human never got a turn")


def test_room_survives_a_restart():
    server = fakeredis.FakeServer()

    async def run() -> None:
        first = RoomManager(store=make_store(server))
        room = first.create("room1", "PRIVATE", RoomConfig(**FAST, bot_levels=[None, 2, 2, 2]),
                            None, "ABC123")
        seat = room.join(None, "我")
        await room.start()
        # play a few of the human's turns so the hand has a history
        for _ in range(3):
            await _wait_for_human(room, seat)
            async with room.lock:
                legal = get_legal_actions(room.game, seat)
                pick = next((a for a in legal if a.type.name == "PASS"), legal[0])
                await room._apply(seat, pick)
        await _wait_for_human(room, seat)
        await asyncio.sleep(0.05)  # let the snapshot writer finish
        before = masked_state(room.game, None)
        hands_before = [list(h) for h in room.game.hands]
        await first.shutdown()

        second = RoomManager(store=make_store(server))
        assert await second.restore() == 1
        back = second.get("room1")
        assert back is not None and back.code == "ABC123" and back.status == "IN_GAME"
        assert second.get_by_code("ABC123") is back
        assert masked_state(back.game, None) == before
        assert [list(h) for h in back.game.hands] == hands_before
        assert back.seats[seat].name == "我" and back.seats[seat].disconnected_at is not None
        assert all(back.seats[i].is_bot for i in range(4) if i != seat)
        # the restored table keeps playing: the human's request is still pending
        assert seat in acting_players(back.game)
        async with back.lock:
            legal = get_legal_actions(back.game, seat)
            await back._apply(seat, legal[0])
        await second.shutdown()

    asyncio.run(run())


def test_finished_rooms_are_not_restored():
    server = fakeredis.FakeServer()

    async def run() -> None:
        store = make_store(server)
        await store.save("done", {"id": "done", "status": "GAME_END"})
        mgr = RoomManager(store=make_store(server))
        assert await mgr.restore() == 0
        assert await store.load("done") is None

    asyncio.run(run())


def test_remote_spectator_relay_and_seat_redirect(client):
    server = fakeredis.FakeServer()
    client.app.state.rooms.store = make_store(server, "this")
    other = make_store(server, "other")
    public = {"room_id": "far", "code": "FAR001", "status": "IN_GAME", "seats": []}

    asyncio.run(other.save("far", {"id": "far", "status": "IN_GAME", "public": public}))
    asyncio.run(other.set_view("far", {"turn": 2}))
    with client.websocket_connect("/ws/game/far") as ws:
        assert ws.receive_json() == {"type": "ROOM_STATE", "payload": {**public}}
        assert ws.receive_json() == {"type": "STATE_UPDATE", "payload": {"turn": 2}}
        # the relay subscribes asynchronously, so keep publishing until it arrives
        stop = threading.Event()

        def publish() -> None:
            pub = make_store(server, "other")
            while not stop.is_set():
                asyncio.run(pub.publish("far", {"type": "PLAYER_ACTION", "payload": {"player": 1}}))
                stop.wait(0.05)

        t = threading.Thread(target=publish, daemon=True)
        t.start()
        try:
            msg = ws.receive_json()
        finally:
            stop.set()
            t.join(2)
        assert msg == {"type": "PLAYER_ACTION", "payload": {"player": 1}}

    from starlette.websockets import WebSocketDisconnect

    from backend.security import create_ws_token

    token = create_ws_token("far", 0, None, "x")
    with pytest.raises(WebSocketDisconnect) as e, \
            client.websocket_connect(f"/ws/game/far?token={token}") as ws:
        ws.receive_json()
    assert e.value.code == 4409
