"""Player progression: levels, bonus, missions, achievements, shop and guest accounts."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend import progression as pg
from backend.models import User, UserProgress
from tests.backend.conftest import auth
from tests.backend.test_rooms_ws import create, play_until_game_end

DAY = datetime(2026, 10, 13, 12, 0, tzinfo=pg.TZ)


def fresh() -> UserProgress:
    return UserProgress(user_id="u1", level=1, xp=0, coins=0, bonus_streak=0, missions=[],
                        achievements=[], owned=["tile_back:jade"], equipped={"tile_back": "jade"},
                        stats={})


def test_level_curve_and_level_up_reward():
    p = fresh()
    events: list[dict] = []
    pg._add_xp(p, 100 + 140, events)  # exactly levels 1→2 (100) and 2→3 (140)
    assert (p.level, p.xp) == (3, 0)
    assert [e["level"] for e in events if e["type"] == "LEVEL_UP"] == [2, 3]
    assert p.coins == 2 * 20 + 3 * 20


def test_daily_bonus_streak_and_reset():
    p = fresh()
    assert pg.claim_bonus(p, DAY) == 500
    with pytest.raises(ValueError):
        pg.claim_bonus(p, DAY)
    assert pg.claim_bonus(p, DAY + timedelta(days=1)) == 550
    assert pg.bonus_status(p, DAY + timedelta(days=3))["amount"] == 500  # streak broken
    for d in range(2, 9):
        pg.claim_bonus(p, DAY + timedelta(days=d))
    assert p.bonus_streak == 9 and pg.bonus_status(p, DAY + timedelta(days=9))["amount"] == 800


def test_daily_missions_are_fixed_per_day_and_claimable():
    p = fresh()
    pg.ensure_today(p, DAY)
    first = [m["id"] for m in p.missions]
    pg.ensure_today(p, DAY + timedelta(hours=5))
    assert [m["id"] for m in p.missions] == first and len(first) == 3
    mission = first[0]
    with pytest.raises(ValueError):
        pg.claim_mission(p, mission, DAY)
    events: list[dict] = []
    pg._bump(p, mission, pg.MISSIONS[mission].target, events)
    assert events[0]["type"] == "MISSION_DONE"
    assert pg.claim_mission(p, mission, DAY) == pg.MISSIONS[mission].reward
    with pytest.raises(ValueError):
        pg.claim_mission(p, mission, DAY)


def test_shop_buy_and_equip_rules():
    p = fresh()
    with pytest.raises(ValueError):
        pg.buy(p, "tile_back", "sapphire")  # 800 coins needed
    p.coins = 1000
    assert pg.buy(p, "tile_back", "sapphire") == 800 and p.coins == 200
    with pytest.raises(ValueError):
        pg.buy(p, "tile_back", "sapphire")
    with pytest.raises(KeyError):
        pg.buy(p, "tile_back", "nope")
    with pytest.raises(ValueError):
        pg.equip(p, "tile_back", "gilded")
    pg.equip(p, "tile_back", "sapphire")
    assert p.equipped["tile_back"] == "sapphire"


def test_hand_rewards_and_achievements():
    p = fresh()

    class FakeDb:
        def get(self, *_):
            return p

    user = User(id="u1", username="x", email="x@x", elo_human=1500)
    win = {"kind": "HU", "winner": 2, "self_draw": True,
           "tai_breakdown": [{"id": "T24", "tai": 8}, {"id": "T04", "tai": 2}]}
    events = pg.record_hand(FakeDb(), user, 2, win, declared=True, now=DAY)  # type: ignore[arg-type]
    kinds = [e["type"] for e in events]
    assert events[0] == {"type": "XP", "xp": 10 + 20 + 2 * 10 + 10}
    unlocked = {e["id"] for e in events if e["type"] == "ACHIEVEMENT"}
    assert {"first_win", "first_tsumo", "ten_tai", "full_flush"} <= unlocked
    assert "LEVEL_UP" not in kinds or p.level >= 1
    match = pg.record_match(FakeDb(), user, 1, now=DAY)  # type: ignore[arg-type]
    assert match[0] == {"type": "MATCH_REWARD", "rank": 1, "coins": 300, "xp": 60}


def test_rank_tiers():
    assert pg.rank_for(1300)["name"] == "新手"
    assert pg.rank_for(1500)["name"] == "熟手" and pg.rank_for(1500)["next"] == "好手"
    assert pg.rank_for(2000) == {"id": "god", "name": "雀神", "next": None, "next_at": None,
                                 "progress": 1.0}


def test_guest_profile_bonus_shop_and_upgrade(client):
    r = client.post("/api/v1/auth/guest")
    assert r.status_code == 201
    token, user = r.json()["token"], r.json()["user"]
    assert user["is_guest"] and user["username"].startswith("訪客")
    prof = client.get("/api/v1/profile/me", headers=auth(token)).json()
    assert prof["level"] == 1 and prof["coins"] == 0 and len(prof["missions"]) == 3
    assert prof["bonus"]["available"] and prof["equipped"]["tile_back"] == "jade"
    assert client.post("/api/v1/profile/bonus", headers=auth(token)).json()["coins"] == 500
    assert client.post("/api/v1/profile/bonus", headers=auth(token)).status_code == 409
    buy = client.post("/api/v1/shop/buy", json={"slot": "tile_back", "item": "sapphire"},
                      headers=auth(token))
    assert buy.status_code == 409  # 500 < 800
    shop = client.get("/api/v1/shop", headers=auth(token)).json()
    assert shop["items"]["tile_back"][0]["equipped"]
    body = {"username": "麥醬玩家", "email": "me@example.com", "password": "secret1"}
    up = client.post("/api/v1/auth/upgrade", headers=auth(token), json=body)
    assert up.status_code == 200 and not up.json()["user"]["is_guest"]
    login = client.post("/api/v1/auth/login",
                        json={"email": "me@example.com", "password": "secret1"})
    assert login.status_code == 200
    again = client.get("/api/v1/profile/me", headers=auth(login.json()["token"])).json()
    assert again["coins"] == 500  # progress kept after upgrading
    assert client.post("/api/v1/auth/upgrade", headers=auth(token), json={
        "username": "x2", "email": "x2@example.com", "password": "secret1"}).status_code == 409


def test_playing_a_match_grants_progress(client):
    token = client.post("/api/v1/auth/guest").json()["token"]
    room = create(client, [None, 3, 3, 3], token)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    seen: list[str] = []
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        assert ws.receive_json()["type"] == "JOINED"
        client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(token))
        play_until_game_end(ws, j["seat"], seen)
    assert "PROGRESS" in seen
    prof = client.get("/api/v1/profile/me", headers=auth(token)).json()
    assert prof["stats"]["hands"] >= 4 and prof["stats"]["matches"] == 1
    assert prof["coins"] >= 40 and (prof["level"] > 1 or prof["xp"] > 0)
