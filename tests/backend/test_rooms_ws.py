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
    assert "NEXT_HAND_IN" in log  # a full round has more than one hand

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


def test_hint_request_returns_ranked_candidates(client):
    room = create(client, [None, 1, 1, 1])
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        client.post(f"/api/v1/rooms/{room['room_id']}/start")
        while True:
            msg = ws.receive_json()
            if msg["type"] == "ACTION_REQUEST" and any(
                    a["action_type"] == "DISCARD" for a in msg["payload"]["legal_actions"]):
                break
            if msg["type"] == "ACTION_REQUEST":
                ws.send_json({"type": "ACTION", "payload": msg["payload"]["legal_actions"][-1]})
        ws.send_json({"type": "HINT_REQUEST"})
        while (msg := ws.receive_json())["type"] != "HINT_RESULT":
            pass
        cands = msg["payload"]["candidates"]
        assert cands and "建議打" in msg["payload"]["explanation"]
        assert [c["shanten_after"] for c in cands] == sorted(c["shanten_after"] for c in cands)
        ws.send_json({"type": "HINT_REQUEST"})  # immediately again: cooldown
        while (msg := ws.receive_json())["type"] != "ERROR":
            pass
        assert msg["payload"]["code"] == "HINT_COOLDOWN"


def test_every_request_carries_the_deadline_when_timed(client):
    token, _ = register(client)
    room = create(client, [None, 1, 1, 1], token, time_limit=30)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    seen = 0
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(token))
        while seen < 12:
            msg = ws.receive_json()
            if msg["type"] in ("WIN_DECLARED", "ROUND_DRAW", "GAME_END"):
                break
            if msg["type"] == "ACTION_REQUEST" and msg["payload"]["player"] == j["seat"]:
                assert msg["payload"]["deadline"] is not None
                seen += 1
                legal = msg["payload"]["legal_actions"]
                # never declare ready: a ready hand's forced discards are auto-played, untimed
                pick = next((a for a in legal if a["action_type"] == "PASS"), None) \
                    or next((a for a in legal if a["action_type"] == "DISCARD"), None) or legal[0]
                ws.send_json({"type": "ACTION", "payload": pick})
    assert seen > 0



def test_join_handshake_and_timeout_notice(client):
    token, _ = register(client)
    room = create(client, [None, 1, 1, 1], token, time_limit=1)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        assert ws.receive_json()["type"] == "JOINED"
        ws.send_json({"type": "JOIN", "payload": {"seat": j["seat"]}})
        while (msg := ws.receive_json())["type"] != "JOINED":
            pass
        assert msg["payload"]["seat"] == j["seat"] and msg["payload"]["room_code"] == room["code"]
        client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(token))
        # never answer: the 1 s clock runs out and the server says so before moving for us
        while True:
            msg = ws.receive_json()
            if msg["type"] == "ERROR":
                assert msg["payload"]["code"] == "TIMEOUT"
                break
            assert msg["type"] not in ("WIN_DECLARED", "ROUND_DRAW", "GAME_END")


def test_quick_match_pairs_players_within_200_rating(client):
    from backend.models import User

    def player(name: str, elo: float) -> str:
        token, info = register(client, name)
        with dbmod.session_factory()() as db:
            u = db.get(User, info["id"])
            assert u is not None
            u.elo_human = elo
            db.commit()
        return token

    def quick(token: str | None) -> dict:
        headers = auth(token) if token else {}
        r = client.post("/api/v1/rooms/quick/join", json={"name": "Q"}, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()

    first = quick(player("alice", 1500))
    near = quick(player("bob", 1650))  # 150 away: same table
    far = quick(player("carol", 1900))  # 325 away from the table's 1575 average: new table
    guest = quick(None)  # no account counts as 1500
    assert near["room"]["room_id"] == first["room"]["room_id"]
    assert far["room"]["room_id"] != first["room"]["room_id"]
    assert guest["room"]["room_id"] == first["room"]["room_id"]
    assert quick(player("dave", 1450))["room"]["room_id"] == first["room"]["room_id"]
    # the first table is now full and has started; the next 1500 player gets a new one
    nxt = quick(player("erin", 1500))
    assert nxt["room"]["room_id"] not in (first["room"]["room_id"], far["room"]["room_id"])


def test_malformed_messages_keep_the_connection(client):
    token, _ = register(client)
    room = create(client, [None, 1, 1, 1], token)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        assert ws.receive_json()["type"] == "JOINED"
        ws.send_text("{not json")
        while (msg := ws.receive_json())["type"] != "ERROR":
            pass
        assert msg["payload"]["code"] == "BAD_MESSAGE"
        for bad in ({"type": "CHAT", "payload": "x"}, {"type": "ACTION", "payload": ["x"]},
                    {"type": "HINT_REQUEST", "payload": 3}):
            ws.send_json(bad)
        ws.send_json({"type": "PING"})
        while (msg := ws.receive_json())["type"] != "PONG":
            pass  # still connected and answering


def test_rate_limited_move_is_asked_for_again(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_WS_PER_SEC", "2")
    token, _ = register(client)
    room = create(client, [None, 1, 1, 1], token)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(token))
        while not ((msg := ws.receive_json())["type"] == "ACTION_REQUEST"
                   and msg["payload"]["player"] == j["seat"]):
            pass
        for _ in range(4):  # well over 2 per second; nothing legal, so no move is made
            ws.send_json({"type": "ACTION", "payload": {"action_type": "PON", "tile": 0}})
        limited = False
        while True:
            msg = ws.receive_json()
            if msg["type"] == "ERROR" and msg["payload"]["code"] == "RATE_LIMIT":
                limited = True
            elif limited and msg["type"] == "ACTION_REQUEST" \
                    and msg["payload"]["player"] == j["seat"]:
                break  # asked again after the dropped move


def test_players_already_waiting_see_a_newcomer(client):
    room = create(client, [None, None, 2, 3])
    url = f"/ws/game/{room['room_id']}?token="
    a = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={"name": "A"}).json()
    with client.websocket_connect(url + a["ws_token"]) as ws_a:
        assert ws_a.receive_json()["type"] == "JOINED"
        ws_a.send_json({"type": "PING"})
        while ws_a.receive_json()["type"] != "PONG":  # drain A's own initial sync
            pass
        b = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={"name": "B"}).json()
        with client.websocket_connect(url + b["ws_token"]) as ws_b:
            assert ws_b.receive_json()["type"] == "JOINED"
            ws_a.send_json({"type": "PING"})
            first = ws_a.receive_json()  # the newcomer must arrive before the reply to our ping
            assert first["type"] == "ROOM_STATE", first["type"]
            seats = first["payload"]["seats"]
            assert seats[b["seat"]]["name"] == "B"


def test_hand_saved_is_announced_once_the_replay_can_be_opened(client):
    room = create(client, [None, 3, 3, 3])
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}).json()
    seen: list[str] = []
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        client.post(f"/api/v1/rooms/{room['room_id']}/start")
        while True:
            msg = ws.receive_json()
            seen.append(msg["type"])
            if msg["type"] == "HAND_SAVED":
                game_id = msg["payload"]["game_id"]
                # the link the result screen shows must open right away
                assert client.get(f"/api/v1/games/{game_id}/frames").status_code == 200
                break
            assert msg["type"] != "GAME_END", "the hand ended without HAND_SAVED"
            if msg["type"] == "ACTION_REQUEST" and msg["payload"]["player"] == j["seat"]:
                legal = msg["payload"]["legal_actions"]
                pick = next((a for a in legal if a["action_type"] == "PASS"), legal[0])
                ws.send_json({"type": "ACTION", "payload": pick})
    end = max(seen.index(k) for k in ("WIN_DECLARED", "ROUND_DRAW") if k in seen)
    assert seen.index("HAND_SAVED") > end
