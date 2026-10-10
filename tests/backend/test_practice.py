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
