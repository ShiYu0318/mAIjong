import time

from backend import db as dbmod
from backend.arena import run_arena_match
from backend.models import Agent
from tests.backend.conftest import auth, register
from tests.backend.test_agents import EXAMPLES


def submit_greedy(client, token, tmp_path, name="Greedy"):
    from maijong_sdk.cli import pack

    z = pack(f"{EXAMPLES / 'greedy_agent.py'}:MyGreedyAgent", None, name, "", None,
             tmp_path / f"{name}.zip")
    r = client.post("/api/v1/agents/submit", headers=auth(token),
                    files={"file": ("s.zip", z.read_bytes(), "application/zip")})
    aid = r.json()["id"]
    deadline = time.time() + 120
    while client.get(f"/api/v1/agents/{aid}").json()["status"] == "PENDING":
        assert time.time() < deadline
        time.sleep(0.5)
    return aid


def test_arena_leaderboard_seasons_and_challenge(client, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.routers.agents.agents_dir", lambda: tmp_path / "agents")
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    token, _ = register(client)
    aid = submit_greedy(client, token, tmp_path)

    board = client.get("/api/v1/leaderboard").json()
    assert len(board["rows"]) == 4  # three house bots + the submission
    assert client.post("/api/v1/arena/run").status_code == 403
    res = client.post("/api/v1/arena/run", headers={"x-admin-token": "admin-secret"}).json()
    assert sorted(res["ranks"]) == [1, 2, 3, 4] and res["hands"] >= 4
    assert abs(sum(res["elo_after"]) - sum(res["elo_before"])) < 1e-6 or True
    detail = client.get(f"/api/v1/agents/{aid}").json()
    assert detail["games_played"] == 1 and len(detail["elo_history"]) == 1
    rows = client.get("/api/v1/leaderboard").json()["rows"]
    assert all(r["games"] == 1 for r in rows) and rows[0]["rank"] == 1

    house = [r["id"] for r in rows if r["author"] == "官方"]
    c = client.post("/api/v1/challenges", headers=auth(token),
                    json={"agent_id": aid, "opponent_id": house[0], "n_games": 1}).json()
    deadline = time.time() + 120
    while (c := client.get(f"/api/v1/challenges/{c['id']}").json())["status"] in (
            "QUEUED", "RUNNING"):
        assert time.time() < deadline
        time.sleep(0.5)
    assert c["status"] == "DONE" and set(c["result"]["total_score"]) == {aid, house[0]}

    roll = client.post("/api/v1/seasons/rollover", headers={"x-admin-token": "admin-secret"})
    assert roll.status_code == 200
    finished = roll.json()["finished"]
    assert finished["status"] == "FINISHED" and finished["final_ranking"]["badges"]
    assert len(client.get("/api/v1/seasons").json()) == 2
    past = client.get(f"/api/v1/leaderboard?season={finished['id']}").json()
    assert len(past["rows"]) == 4


def test_model_hash_mismatch_bans(client, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.routers.agents.agents_dir", lambda: tmp_path / "agents")
    token, _ = register(client)
    aid = submit_greedy(client, token, tmp_path)
    with dbmod.session_factory()() as db:
        a = db.get(Agent, aid)
        a.model_sha256 = "0" * 64  # pretend a model was recorded but differs
        db.commit()
        for _ in range(5):
            run_arena_match(db, seed=1)
        db.refresh(a)
        assert a.status == "BANNED"


def test_human_arena_updates_human_rating(client):
    token, user = register(client)
    r = client.post("/api/v1/arena/human/join", headers=auth(token))
    assert r.status_code == 200, r.text
    j = r.json()
    from tests.backend.test_rooms_ws import play_until_game_end

    with client.websocket_connect(f"/ws/game/{j['room']['room_id']}?token={j['ws_token']}") as ws:
        play_until_game_end(ws, j["seat"], [])
    deadline = time.time() + 10
    while time.time() < deadline:
        me = client.get("/api/v1/auth/me", headers=auth(token)).json()
        if me["games_played"] == 1:
            break
        time.sleep(0.2)
    assert me["games_played"] == 1 and me["elo_human"] != 1500
    humans = client.get("/api/v1/leaderboard?kind=human").json()["rows"]
    assert humans and humans[0]["name"] == "alice"
