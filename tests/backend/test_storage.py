"""Replay storage: local folder by default, MinIO/S3 with presigned URLs (SPEC P6-2)."""

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
