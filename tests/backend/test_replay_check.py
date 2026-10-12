"""Replay verification (SPEC 11): saved hands re-run to the same events and result."""

from __future__ import annotations

import gzip
import json
import time

from sqlalchemy import select

from backend import db as dbmod
from backend.models import Game
from backend.replay_check import verify_game, verify_pending
from backend.storage import get_storage
from tests.backend.conftest import auth, register
from tests.backend.test_rooms_ws import create, play_until_game_end


def _games(expected: int) -> list[Game]:
    deadline = time.time() + 10
    while True:
        with dbmod.session_factory()() as db:
            games = list(db.scalars(select(Game)).all())
        if len(games) >= expected or time.time() > deadline:
            return games
        time.sleep(0.1)


def test_every_saved_hand_is_verified(client):
    token, _ = register(client)
    room = create(client, [None, 1, 3, 3], token)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(token))
        play_until_game_end(ws, j["seat"], [])
    games = _games(4)
    assert len(games) >= 4
    assert all(g.replay_verified is True for g in games)


def test_tampered_replay_fails_and_sweep_counts_it(client):
    token, _ = register(client)
    room = create(client, [None, 1, 1, 1], token)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(token))
        play_until_game_end(ws, j["seat"], [])
    gid = _games(1)[0].id
    storage = get_storage()
    lines = gzip.decompress(storage.get(gid)).decode().splitlines()
    meta = json.loads(lines[0])
    meta["result"] = {**meta["result"], "payments": [999, -333, -333, -333]}
    storage.put(gid, gzip.compress(("\n".join([json.dumps(meta)] + lines[1:]) + "\n").encode()))
    with dbmod.session_factory()() as db:
        game = db.get(Game, gid)
        assert game is not None
        assert verify_game(db, game) is False
        assert game.replay_verified is False
        for g in db.scalars(select(Game)).all():
            g.replay_verified = None
        db.commit()
        counts = verify_pending(db)
        assert counts["checked"] >= 4 and counts["failed"] == 1
        assert counts["passed"] == counts["checked"] - 1
        assert verify_pending(db)["checked"] == 0  # nothing left unchecked


def test_practice_scenario_hand_is_verified(client):
    cat = client.get("/api/v1/practice/scenarios").json()
    sc = cat[0]
    j = client.post(f"/api/v1/practice/scenarios/{sc['id']}/play").json()
    with client.websocket_connect(f"/ws/game/{j['room']['room_id']}?token={j['ws_token']}") as ws:
        play_until_game_end(ws, j["seat"], [])
    games = _games(1)
    assert len(games) == 1 and games[0].replay_verified is True
    frames = client.get(f"/api/v1/games/{games[0].id}/frames")
    assert frames.status_code == 200  # the replay viewer can rebuild it too
