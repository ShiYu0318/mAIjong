"""Prometheus metrics endpoint and optional Sentry setup (SPEC 12)."""

from __future__ import annotations

import re

from backend.metrics import celery_queue_depth
from backend.observability import init_sentry
from tests.backend.conftest import auth, register
from tests.backend.test_rooms_ws import create, play_until_game_end


def _value(text: str, name: str) -> float:
    m = re.search(rf"^{re.escape(name)} (\S+)$", text, re.M)
    return float(m.group(1)) if m else 0.0


def _hands(text: str) -> float:
    pattern = r'^maijong_hands_total\{kind="\w+"\} (\S+)$'
    return sum(float(v) for v in re.findall(pattern, text, re.M))


def test_metrics_count_hands_matches_and_sockets(client):
    before = client.get("/metrics")
    assert before.status_code == 200 and before.headers["content-type"].startswith("text/plain")
    assert "# TYPE maijong_hands_total counter" in before.text
    token, _ = register(client)
    room = create(client, [None, 1, 1, 1], token)
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}, headers=auth(token)).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        ws.receive_json()
        during = client.get("/metrics").text
        ws_before = _value(before.text, "maijong_ws_connections")
        assert _value(during, "maijong_ws_connections") == ws_before + 1
        assert _value(during, 'maijong_rooms{state="all"}') >= 1
        client.post(f"/api/v1/rooms/{room['room_id']}/start", headers=auth(token))
        play_until_game_end(ws, j["seat"], [])
    after = client.get("/metrics").text
    assert _hands(after) >= _hands(before.text) + 4
    matches_before = _value(before.text, "maijong_matches_total")
    assert _value(after, "maijong_matches_total") == matches_before + 1
    assert _value(after, "maijong_ws_connections") == _value(before.text, "maijong_ws_connections")
    assert "maijong_celery_queue_depth" not in after  # no Redis broker configured


def test_metrics_token(client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "s3cret")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_sentry_is_optional(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry() is False
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.invalid/1")
    assert init_sentry() is False  # sentry-sdk is not a dependency; this only warns
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    assert celery_queue_depth() is None
