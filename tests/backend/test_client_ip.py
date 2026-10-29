"""Behind a proxy every player shares the proxy's address; the real one comes from a header
the proxy sets, and only when that header is configured as trusted."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.security_middleware import SecurityMiddleware


def _app() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)

    @app.post("/api/v1/auth/login")
    def login() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def _codes(client: TestClient, headers: dict[str, str], n: int) -> list[int]:
    return [client.post("/api/v1/auth/login", headers=headers).status_code for _ in range(n)]


def test_trusted_header_gives_each_player_their_own_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MIN", "2")
    monkeypatch.setenv("TRUSTED_PROXY_HEADER", "CF-Connecting-IP")
    c = _app()
    assert _codes(c, {"CF-Connecting-IP": "203.0.113.1"}, 3) == [200, 200, 429]
    assert _codes(c, {"CF-Connecting-IP": "203.0.113.2"}, 2) == [200, 200]  # someone else


def test_header_is_ignored_unless_trusted(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MIN", "2")
    monkeypatch.delenv("TRUSTED_PROXY_HEADER", raising=False)
    c = _app()
    # a client can't dodge the limit by inventing addresses
    codes = [c.post("/api/v1/auth/login",
                    headers={"CF-Connecting-IP": f"198.51.100.{i}"}).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]


def test_forwarded_for_uses_the_address_the_proxy_appended(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MIN", "2")
    monkeypatch.setenv("TRUSTED_PROXY_HEADER", "X-Forwarded-For")
    c = _app()
    # the left part is whatever the client sent; the proxy appends the real address
    codes = [c.post("/api/v1/auth/login",
                    headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"}).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]
