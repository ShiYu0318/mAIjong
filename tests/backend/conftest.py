from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("REPLAY_DIR", str(tmp_path / "replays"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough-123")
    from backend import config, db

    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.session_factory.cache_clear()
    from backend.main import create_app

    with TestClient(create_app()) as c:
        yield c
    db.get_engine().dispose()
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.session_factory.cache_clear()


def register(client: TestClient, name: str = "alice") -> tuple[str, dict]:
    r = client.post("/api/v1/auth/register",
                    json={"username": name, "email": f"{name}@example.com", "password": "secret1"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["token"], body["user"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
