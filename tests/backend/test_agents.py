import time
from pathlib import Path

from maijong_sdk.cli import pack

from tests.backend.conftest import auth, register

EXAMPLES = Path(__file__).resolve().parents[2] / "sdk" / "examples"


def test_submit_validate_list_delete(client, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.routers.agents.agents_dir", lambda: tmp_path / "agents")
    token, _ = register(client)
    z = pack(f"{EXAMPLES / 'greedy_agent.py'}:MyGreedyAgent", None, "Greedy", "demo", None,
             tmp_path / "s.zip")
    files = {"file": ("submission.zip", z.read_bytes(), "application/zip")}
    assert client.post("/api/v1/agents/submit", files=files).status_code == 401
    r = client.post("/api/v1/agents/submit", files=files, headers=auth(token))
    assert r.status_code == 201, r.text
    agent = r.json()
    assert agent["status"] == "PENDING" and agent["version"] == 1
    deadline = time.time() + 120
    while time.time() < deadline:
        a = client.get(f"/api/v1/agents/{agent['id']}").json()
        if a["status"] != "PENDING":
            break
        time.sleep(0.5)
    assert a["status"] == "ACTIVE", a["validation"]
    assert any(x["id"] == agent["id"] for x in client.get("/api/v1/agents").json())
    again = client.post("/api/v1/agents/submit", files=files, headers=auth(token)).json()
    assert again["version"] == 2
    other, _ = register(client, "bob")
    assert client.delete(f"/api/v1/agents/{agent['id']}", headers=auth(other)).status_code == 403
    assert client.delete(f"/api/v1/agents/{agent['id']}", headers=auth(token)).status_code == 204


def test_bad_zip(client):
    token, _ = register(client)
    files = {"file": ("x.zip", b"not a zip", "application/zip")}
    assert client.post("/api/v1/agents/submit", files=files, headers=auth(token)).status_code == 422
