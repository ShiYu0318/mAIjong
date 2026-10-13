from backend.security_middleware import TokenBucket, clean_text


def test_security_headers(client):
    r = client.get("/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_auth_rate_limit(client):
    codes = [client.post("/api/v1/auth/login",
                         json={"email": "a@example.com", "password": "nopenope"}).status_code
             for _ in range(14)]
    assert 429 in codes and codes[0] == 401


def test_token_bucket_and_clean_text():
    b = TokenBucket(2, 60)
    assert b.allow("x") and b.allow("x") and not b.allow("x")
    assert clean_text("hi\x00 there\x1b[31m") == "hi there[31m"
    assert len(clean_text("a" * 500)) == 200


def _preflight(client, origin: str):
    return client.options("/api/v1/rooms/quick/join", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization"})


def test_dev_cors_allows_local_and_lan_pages_only(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000", "http://172.20.10.8:3000",
                   "http://192.168.1.20:3000", "http://10.0.0.5:3001"):
        r = _preflight(client, origin)
        assert r.status_code == 200, origin
        assert r.headers["access-control-allow-origin"] == origin
    for origin in ("https://evil.example", "http://172.32.0.1:3000", "http://8.8.8.8:3000"):
        assert _preflight(client, origin).status_code == 400, origin


def test_origin_regex_can_be_switched_off(monkeypatch):
    from backend import config

    monkeypatch.setenv("CORS_ORIGIN_REGEX", "")
    config.get_settings.cache_clear()
    try:
        assert config.get_settings().cors_origin_regex is None
    finally:
        config.get_settings.cache_clear()
    monkeypatch.delenv("CORS_ORIGIN_REGEX")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/maijong")
    config.get_settings.cache_clear()
    try:
        assert config.get_settings().cors_origin_regex is None  # production: explicit list only
    finally:
        config.get_settings.cache_clear()
