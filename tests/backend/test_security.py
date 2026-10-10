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
