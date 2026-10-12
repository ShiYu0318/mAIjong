import time

from backend.tasks.runner import binomial_p_value


def wait_job(client, job_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = client.get(f"/api/v1/lab/jobs/{job_id}").json()
        if j["status"] in ("DONE", "FAILED"):
            return j
        time.sleep(0.3)
    raise AssertionError("job did not finish")


def test_simulation_job(client):
    assert "rule" in client.get("/api/v1/lab/agents").json()
    r = client.post("/api/v1/lab/simulate",
                    json={"seats": ["rule", "random", "random", "random"], "n_games": 12})
    assert r.status_code == 202
    job = wait_job(client, r.json()["job_id"])
    assert job["status"] == "DONE", job
    summary = job["metrics"]["summary"]
    assert summary["hands"] == 12 and len(summary["seats"]) == 4
    names = {a["agent"] for a in job["metrics"]["agents"]}
    assert names == {"rule", "random"}
    assert any(j["id"] == job["id"] for j in client.get("/api/v1/lab/jobs").json())


def test_compare_job_and_validation(client):
    r = client.post("/api/v1/lab/compare", json={"agents": ["rule", "random"], "n_games": 8})
    job = wait_job(client, r.json()["job_id"])
    assert job["config"]["seats"] == ["rule", "random", "rule", "random"]
    assert all(0 <= a["p_value"] <= 1 for a in job["metrics"]["agents"])
    bad = client.post("/api/v1/lab/simulate", json={"seats": ["nope"] * 4, "n_games": 1})
    assert bad.status_code == 422
    assert client.get("/api/v1/lab/jobs/missing").status_code == 404


def test_replay_explorer_filters(client):
    from tests.backend.test_rooms_ws import create

    room = create(client, [3, 3, 3, 3], public=True, bot_delay=0)
    client.post(f"/api/v1/rooms/{room['room_id']}/start")
    deadline = time.time() + 30
    rows = []
    while time.time() < deadline and not rows:
        rows = client.get("/api/v1/lab/replays").json()
        time.sleep(0.3)
    assert rows
    draws = client.get("/api/v1/lab/replays?result=DRAW").json()
    assert all(r["result"]["kind"] == "DRAW" for r in draws)
    big = client.get("/api/v1/lab/replays?min_tai=99").json()
    assert big == []


def test_binomial_p_value():
    assert binomial_p_value(50, 100, 0.5) > 0.9
    assert binomial_p_value(90, 100, 0.5) < 1e-10


def test_runs_listing_and_incremental_series(client, tmp_path, monkeypatch):
    from ai.training import metrics

    monkeypatch.setattr(metrics, "RUNS_DIR", tmp_path / "runs")
    logger = metrics.MetricsLogger("cli-run", {"kind": "sb3_maskable_ppo"})
    for step in (1, 2, 3):
        logger.log(step, eval_win_rate=0.1 * step)
    logger.close()
    rows = client.get("/api/v1/lab/runs").json()
    assert rows[0]["name"] == "cli-run" and rows[0]["kind"] == "sb3_maskable_ppo"
    assert rows[0]["points"] == 3 and abs(rows[0]["eval_win_rate"] - 0.3) < 1e-9
    full = client.get("/api/v1/lab/runs/cli-run").json()
    assert [p["step"] for p in full["series"]] == [1, 2, 3]
    newer = client.get("/api/v1/lab/runs/cli-run?since=2").json()
    assert [p["step"] for p in newer["series"]] == [3]
    assert client.get("/api/v1/lab/runs/..").status_code == 404
    assert client.get("/api/v1/lab/runs/missing").status_code == 404


def test_sb3_training_arguments():
    from backend.tasks import runner

    args = runner._train_args("job1", "sb3", {"steps": 5000, "bc_data": "data/x.jsonl.gz"})
    assert args[2] == "ai.training.sb3_trainer"
    assert args[args.index("--steps") + 1] == "5000"
    assert args[args.index("--bc-data") + 1] == "data/x.jsonl.gz"
    assert args[args.index("--out-dir") + 1].endswith("checkpoints/sb3_job1")
    assert runner.checkpoint_for("job1", "sb3").name == "sb3_best.zip"
