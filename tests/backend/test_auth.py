from tests.backend.conftest import auth, register


def test_register_login_me(client):
    token, user = register(client)
    assert user["username"] == "alice" and user["elo_human"] == 1500
    r = client.get("/api/v1/auth/me", headers=auth(token))
    assert r.status_code == 200 and r.json()["id"] == user["id"]
    creds = {"email": "alice@example.com", "password": "secret1"}
    r = client.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200 and r.json()["token"]


def test_duplicate_and_bad_credentials(client):
    register(client)
    r = client.post("/api/v1/auth/register",
                    json={"username": "alice", "email": "x@example.com", "password": "secret1"})
    assert r.status_code == 409
    r = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "nope00"})
    assert r.status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth("garbage")).status_code == 401


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}
