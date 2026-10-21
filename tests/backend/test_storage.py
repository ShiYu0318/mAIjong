"""Replay storage: local folder by default, S3-compatible store with presigned URLs (SPEC P6-2)."""

from __future__ import annotations

import gzip

import pytest

pytest.importorskip("moto")

from moto import mock_aws  # noqa: E402

from backend.storage import LocalStorage, S3Storage  # noqa: E402
from tests.backend.test_rooms_ws import create, play_until_game_end  # noqa: E402


def test_local_storage_round_trip(tmp_path):
    st = LocalStorage(tmp_path / "r")
    st.put("g1", b"abc")
    assert st.get("g1") == b"abc" and st.presigned_url("g1") is None
    assert st.location("g1").endswith("g1.jsonl.gz")
    with pytest.raises(FileNotFoundError):
        st.get("missing")
    with pytest.raises(ValueError):
        st.put("../evil", b"x")


@mock_aws
def test_replays_in_s3_with_presigned_urls(client, monkeypatch):
    import boto3

    s3 = S3Storage(boto3.client("s3", region_name="us-east-1"), "maijong-test")
    import backend.persistence as persistence
    import backend.routers.games as games

    monkeypatch.setattr(persistence, "get_storage", lambda: s3)
    monkeypatch.setattr(games, "get_storage", lambda: s3)

    room = create(client, [None, 3, 3, 3])
    j = client.post(f"/api/v1/rooms/{room['room_id']}/join", json={}).json()
    with client.websocket_connect(f"/ws/game/{room['room_id']}?token={j['ws_token']}") as ws:
        client.post(f"/api/v1/rooms/{room['room_id']}/start")
        play_until_game_end(ws, j["seat"], [])

    keys = [o["Key"] for o in s3.s3.list_objects_v2(Bucket="maijong-test")["Contents"]]
    assert keys and all(k.startswith("replays/") for k in keys)
    game_id = keys[0].removeprefix("replays/").removesuffix(".jsonl.gz")

    url = client.get(f"/api/v1/games/{game_id}/replay").json()["url"]
    assert "maijong-test" in url and "Signature" in url
    frames = client.get(f"/api/v1/games/{game_id}/frames")
    assert frames.status_code == 200 and frames.json()["frames"]
    raw = client.get(f"/api/v1/games/{game_id}/replay/download")
    assert raw.status_code == 200
    first = gzip.decompress(raw.content).decode().splitlines()[0]
    assert '"type": "META"' in first


@mock_aws
def test_download_links_use_the_public_endpoint(monkeypatch):
    # in docker compose the backend reaches S3 as http://s3:8333, which a browser cannot
    import backend.storage as storage
    from backend.config import get_settings

    monkeypatch.setenv("S3_ENDPOINT", "http://s3:8333")
    monkeypatch.setenv("S3_PUBLIC_ENDPOINT", "http://localhost:8333")
    monkeypatch.setenv("S3_BUCKET", "maijong-test")
    monkeypatch.setenv("S3_ACCESS_KEY", "k")
    monkeypatch.setenv("S3_SECRET_KEY", "s")
    get_settings.cache_clear()
    storage.get_storage.cache_clear()
    monkeypatch.setattr(storage.S3Storage, "_ensure_bucket", lambda self: None)
    try:
        st = storage.get_storage()
        assert isinstance(st, S3Storage)
        assert st.s3.meta.endpoint_url == "http://s3:8333"
        assert st.presigned_url("g1").startswith("http://localhost:8333/maijong-test/replays/g1")
    finally:
        get_settings.cache_clear()
        storage.get_storage.cache_clear()
