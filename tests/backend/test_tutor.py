from engine import tiles
from tests.backend.conftest import auth, register
from tests.backend.test_rooms_ws import create

P = tiles.parse


def test_analyze_tenpai_and_discards(client):
    r = client.post("/api/v1/tutor/analyze", json={"hand": P("123m 456m 789m 111p 57s 東東")})
    assert r.status_code == 200
    body = r.json()
    assert body["shanten"] == 0 and [w["name"] for w in body["waits"]] == ["6條"]
    assert body["waits"][0]["tai"] == 2  # 門清 + 中洞
    r = client.post("/api/v1/tutor/analyze", json={"hand": P("123m 456m 789m 111p 57s 東東 北")})
    assert r.json()["discards"][0]["name"] == "北"
    r = client.post("/api/v1/tutor/analyze", json={"hand": P("123m")})
    assert r.status_code == 422


def test_quiz_round_trip_and_progress(client):
    token, _ = register(client)
    q = client.get("/api/v1/tutor/quiz?difficulty=1").json()
    hand = q["position"]["hand"]
    r = client.post("/api/v1/tutor/quiz/answer", headers=auth(token),
                    json={"quiz_token": q["quiz_token"], "tile": hand[0]})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] in ("best", "good", "worse") and body["explanation"]
    prog = client.get("/api/v1/tutor/progress", headers=auth(token)).json()
    assert any(p["lesson_id"] == "quiz" for p in prog)
    r = client.put("/api/v1/tutor/progress/tiles", headers=auth(token),
                   json={"status": "COMPLETED", "quiz_score": 1})
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"
    assert client.post("/api/v1/tutor/quiz/answer",
                       json={"quiz_token": "bad", "tile": 0}).status_code == 400
    assert len(client.get("/api/v1/tutor/lessons").json()) == 8


def test_guided_game_sends_coach_notes(client):
    room = create(client, [None, 1, 1, 1], tutor=True)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        client.post(f"/api/v1/rooms/{room['room_id']}/start")
        notes = []
        for _ in range(400):
            msg = ws.receive_json()
            if msg["type"] == "TUTOR_NOTE":
                notes.append(msg["payload"])
                if len(notes) >= 2:
                    break
            if msg["type"] == "ACTION_REQUEST" and msg["payload"]["player"] == j["seat"]:
                legal = msg["payload"]["legal_actions"]
                pick = next((a for a in legal if a["action_type"] == "PASS"), legal[0])
                ws.send_json({"type": "ACTION", "payload": pick})
    assert len(notes) >= 2 and all(n["text"] for n in notes)
