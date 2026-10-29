import time

from tests.backend.test_rooms_ws import create


def test_disconnect_takeover_and_reconnect(client, monkeypatch):
    from backend import config

    monkeypatch.setenv("GRACE_PERIOD_SEC", "0.2")
    config.get_settings.cache_clear()
    room = create(client, [None, 3, 3, 3], time_limit=None, bot_delay=0.05)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={"name": "me"}).json()
    url = f"/ws/game/{room['room_id']}?token={j['ws_token']}"
    with client.websocket_connect(url) as ws:
        ws.receive_json()
        assert client.post(f"/api/v1/rooms/{room['room_id']}/start").status_code == 200
        while ws.receive_json()["type"] != "STATE_UPDATE":
            pass
    # socket closed mid-game: after the grace period a bot plays this seat
    deadline = time.time() + 5
    seat = None
    while time.time() < deadline:
        seat = client.get(f"/api/v1/rooms/{room['code']}").json()["seats"][j["seat"]]
        if seat["taken_over"]:
            break
        time.sleep(0.1)
    assert seat and seat["taken_over"]
    # the hand keeps going without us
    time.sleep(0.5)
    info = client.get(f"/api/v1/rooms/{room['code']}").json()
    assert info["status"] in ("IN_GAME", "ROUND_END", "GAME_END")
    # reconnecting within the window gives the seat back
    with client.websocket_connect(url) as ws:
        assert ws.receive_json()["type"] == "JOINED"
        seat = client.get(f"/api/v1/rooms/{room['code']}").json()["seats"][j["seat"]]
        assert not seat["taken_over"]


def test_others_learn_how_long_until_the_ai_takes_over(client, monkeypatch):
    from backend import config

    monkeypatch.setenv("GRACE_PERIOD_SEC", "30")
    config.get_settings.cache_clear()
    room = create(client, [None, None, 3, 3], time_limit=None)
    a = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={"name": "A"}).json()
    b = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={"name": "B"}).json()
    base = f"/ws/game/{room['room_id']}?token="
    with client.websocket_connect(base + a["ws_token"]) as wa:
        wa.receive_json()
        with client.websocket_connect(base + b["ws_token"]) as wb:
            wb.receive_json()
            assert client.post(f"/api/v1/rooms/{room['room_id']}/start").status_code == 200
            while wb.receive_json()["type"] != "STATE_UPDATE":
                pass
        # B left mid-game: A hears it, with the grace period to show a countdown
        while (msg := wa.receive_json())["type"] != "PLAYER_DISCONNECTED":
            pass
        assert msg["payload"] == {"seat": b["seat"], "grace": 30.0}
