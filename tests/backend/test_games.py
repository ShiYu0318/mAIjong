from tests.backend.conftest import auth, register
from tests.backend.test_rooms_ws import create, play_until_game_end


def test_replay_frames_download_and_annotations(client):
    token, user = register(client)
    room = create(client, [None, 1, 2, 3], token)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(token))
        play_until_game_end(ws, j["seat"], [])

    games = client.get(f"/api/v1/users/{user['id']}/games").json()
    assert len(games) >= 4
    gid = games[0]["id"]
    data = client.get(f"/api/v1/games/{gid}/frames").json()
    frames = data["frames"]
    assert frames[0]["action"] is None and len(frames) > 10
    assert frames[-1]["view"]["result"] == data["game"]["result"]
    assert all(p["hand"] is not None for p in frames[1]["view"]["players"])
    assert any(f["decision"] for f in frames)  # bot decisions are kept

    url = client.get(f"/api/v1/games/{gid}/replay").json()["url"]
    r = client.get(url)
    assert r.status_code == 200 and r.headers["content-type"] == "application/gzip"

    assert client.post(f"/api/v1/games/{gid}/annotations", json={"seq": 3, "note": "這裡該碰"}
                       ).status_code == 401
    r = client.post(f"/api/v1/games/{gid}/annotations", headers=auth(token),
                    json={"seq": 3, "note": "這裡該碰"})
    assert r.status_code == 201
    notes = client.get(f"/api/v1/games/{gid}/annotations").json()
    assert notes[0]["note"] == "這裡該碰" and notes[0]["user"] == "alice"
    assert client.get("/api/v1/games/nope/frames").status_code == 404
