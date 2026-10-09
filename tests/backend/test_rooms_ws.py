"""Rooms REST + WebSocket integration: humans and bots play to the end of a match."""

from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import func, select

from backend import db as dbmod
from backend.models import Game, GameEvent
from backend.persistence import read_replay
from tests.backend.conftest import auth, register

FAST = {"time_limit": None, "rounds": 1, "bot_delay": 0, "next_hand_delay": 0}


def create(client, bot_levels, token=None, **cfg) -> dict[str, Any]:
    headers = auth(token) if token else {}
    r = client.post("/api/v1/rooms", headers=headers,
                    json={"type": "PRIVATE", "config": {**FAST, **cfg, "bot_levels": bot_levels}})
    assert r.status_code == 201, r.text
    return r.json()


def play_until_game_end(ws, seat: int, log: list[str]) -> dict[str, Any]:
    """Answer every ACTION_REQUEST with HU if possible, else PASS, else the first action."""
    while True:
        msg = ws.receive_json()
        kind = msg["type"]
        log.append(kind)
        if kind == "GAME_END":
            return msg["payload"]
        if kind == "ACTION_REQUEST" and msg["payload"]["player"] == seat:
            legal = msg["payload"]["legal_actions"]
            pick = next((a for a in legal if a["action_type"] == "HU"), None) \
                or next((a for a in legal if a["action_type"] == "PASS"), None) \
                or legal[0]
            ws.send_json({"type": "ACTION", "payload": pick})


def test_room_lifecycle_rest(client):
    token, _ = register(client)
    room = create(client, [None, 1, 2, 3], token)
    r = client.get(f"/api/v1/rooms/{room['code']}")
    assert r.status_code == 200 and r.json()["status"] == "WAITING"
    r = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token))
    assert r.status_code == 200 and r.json()["seat"] == 0
    # only the host may start
    other, _ = register(client, "bob")
    r = client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(other))
    assert r.status_code == 403
    assert client.get("/api/v1/rooms/NOPE00").status_code == 404


def test_one_human_three_bots_full_match_and_persistence(client):
    room = create(client, [None, 1, 3, 3])
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={"name": "我"}).json()
    seat = j["seat"]
    log: list[str] = []
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        assert ws.receive_json()["type"] == "JOINED"
        assert client.post(f"/api/v1/rooms/{room['room_id']}/start").status_code == 200
        end = play_until_game_end(ws, seat, log)
    assert sum(end["final_scores"]) == 0 and sorted(end["ranks"]) == [1, 2, 3, 4]
    assert "DEAL" in log and "STATE_UPDATE" in log and "ACTION_REQUEST" in log

    with dbmod.session_factory()() as db:
        games = db.scalars(select(Game)).all()
        assert len(games) >= 4  # at least four hands in one round
        n_events = db.scalar(select(func.count()).select_from(GameEvent))
        assert n_events and n_events > 50
        replay = read_replay(games[0].id)
        assert replay[0]["type"] == "META" and replay[1]["type"] == "DEAL"


def test_two_human_clients_and_two_bots(client):
    room = create(client, [None, None, 2, 3])
    joins = [client.post(f"/api/v1/rooms/{room['room_id']}/join", json={"name": n}).json()
             for n in ("A", "B")]
    results: dict[int, Any] = {}
    errors: list[BaseException] = []

    def run(j: dict[str, Any], ws) -> None:
        try:
            results[j["seat"]] = play_until_game_end(ws, j["seat"], [])
        except BaseException as e:  # surface in main thread
            errors.append(e)

    url = f"/ws/game/{room['room_id']}?token="
    with client.websocket_connect(url + joins[0]["ws_token"]) as ws0, \
            client.websocket_connect(url + joins[1]["ws_token"]) as ws1:
        ws0.receive_json()
        ws1.receive_json()
        threads = [threading.Thread(target=run, args=(j, w))
                   for j, w in zip(joins, (ws0, ws1), strict=True)]
        for t in threads:
            t.start()
        assert client.post(f"/api/v1/rooms/{room['room_id']}/start").status_code == 200
        for t in threads:
            t.join(timeout=120)
    assert not errors, errors
    assert results[0]["final_scores"] == results[1]["final_scores"]


def test_invalid_action_and_bad_token(client):
    room = create(client, [None, 1, 1, 1])
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        ws.send_json({"type": "ACTION", "payload": {"action_type": "DISCARD", "tile": 0}})
        msg = ws.receive_json()
        while msg["type"] != "ERROR":
            msg = ws.receive_json()
        assert msg["payload"]["code"] == "INVALID_ACTION"
        ws.send_json({"type": "PING"})
        while ws.receive_json()["type"] != "PONG":
            pass
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect), \
            client.websocket_connect(f"/ws/game/{room['room_id']}?token=bad") as ws:
        ws.receive_json()


def test_quick_join_fills_with_bots(client):
    j = client.post("/api/v1/rooms/quick/join", json={"name": "Q"}).json()
    assert j["room"]["type"] == "QUICK" and j["seat"] == 0
