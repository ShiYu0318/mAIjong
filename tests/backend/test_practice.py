from engine import tiles
from engine.shanten import shanten_after_discards
from tests.backend.test_rooms_ws import play_until_game_end


def test_speed_challenge_reaches_tenpai_or_wall_end(client):
    r = client.post("/api/v1/practice/speed/start").json()
    assert len(r["hand"]) == 17 and not r["done"]
    for _ in range(80):
        after = shanten_after_discards(tiles.to_counts(r["hand"]))
        tile = min(after, key=lambda t: (after[t], t))
        r = client.post("/api/v1/practice/speed/discard",
                        json={"token": r["token"], "tile": tile}).json()
        if r["done"]:
            break
    assert r["done"] and (r["tenpai"] and r["score"] >= 0 or not r["tenpai"])
    bad = client.post("/api/v1/practice/speed/discard", json={"token": "x", "tile": 0})
    assert bad.status_code == 400


def test_defense_drill_runs_to_an_outcome(client):
    r = client.post("/api/v1/practice/defense/start").json()
    assert r["declared"] and not r["done"]
    for _ in range(10):
        # play the safest-looking tile: one already discarded by anyone, else the first
        seen = {t for d in r["discards"] for t in d}
        options = sorted(set(r["hand"]))
        tile = next((t for t in options if t in seen), options[0])
        resp = client.post("/api/v1/practice/defense/discard",
                           json={"token": r["token"], "tile": tile})
        if resp.status_code == 422:  # e.g. the hand already ended for us
            break
        r = resp.json()
        if r["done"]:
            break
    assert r["done"] or r["survived"] >= 1
    if r["done"]:
        assert r["success"] != r["dealt_in"]


def test_scenarios_catalogue_and_play(client):
    cat = client.get("/api/v1/practice/scenarios").json()
    assert len(cat) >= 50 and "seed" not in cat[0]
    sc = next(c for c in cat if c["category"] == "one_away")
    j = client.post(f"/api/v1/practice/scenarios/{sc['id']}/play").json()
    assert j["seat"] == sc["seat"] and j["room"]["type"] == "PRACTICE"
    with client.websocket_connect(f"/ws/game/{j['room']['room_id']}?token={j['ws_token']}") as ws:
        end = play_until_game_end(ws, j["seat"], [])
    assert sorted(end["ranks"]) == [1, 2, 3, 4]


def _first_request(ws, seat):
    while True:
        msg = ws.receive_json()
        if msg["type"] == "ACTION_REQUEST" and msg["payload"]["player"] == seat:
            return msg["payload"]["legal_actions"]


def _await(ws, kind):
    while (msg := ws.receive_json())["type"] != kind:
        pass
    return msg["payload"]


def test_a_scenario_states_its_question_and_judges_the_key_move(client):
    cat = client.get("/api/v1/practice/scenarios").json()
    for category, kind in (("one_away", "discard"), ("call", "call")):
        sc = next(c for c in cat if c["category"] == category)
        j = client.post(f"/api/v1/practice/scenarios/{sc['id']}/play").json()
        assert j["room"]["scenario"] == {"id": sc["id"], "title": sc["title"],
                                         "description": sc["description"], "category": category}
        url = f"/ws/game/{j['room']['room_id']}?token={j['ws_token']}"
        with client.websocket_connect(url) as ws:
            legal = _first_request(ws, j["seat"])
            pick = next((a for a in legal if a["action_type"] == "PASS"), legal[-1])
            ws.send_json({"type": "ACTION", "payload": pick})
            res = _await(ws, "SCENARIO_RESULT")
        assert res["kind"] == kind and res["verdict"] in ("best", "good", "worse")
        assert res["explanation"] and res["best"] and res["chosen"]
        if kind == "discard":
            assert res["chosen"]["tile"] == pick["tile"] and len(res["candidates"]) >= 2
        else:
            assert res["chosen"]["action_type"] == "PASS"
