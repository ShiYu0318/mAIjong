"""Replay file storage (SPEC P6-2): a local folder by default, MinIO / S3 when configured.

S3 settings: S3_ENDPOINT (e.g. http://s3:8333), S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY, and
S3_PUBLIC_ENDPOINT when browsers reach S3 at another address than the backend does (docker
compose: http://localhost:8333); download links are signed for that address.
With S3 the replay endpoint hands out short-lived presigned download URLs.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from backend.config import get_settings

log = logging.getLogger("maijong.storage")
PRESIGN_SECONDS = 3600


class ReplayStorage(Protocol):
    def put(self, game_id: str, data: bytes) -> None: ...
    def get(self, game_id: str) -> bytes: ...
    def presigned_url(self, game_id: str) -> str | None: ...
    def location(self, game_id: str) -> str: ...


def _name(game_id: str) -> str:
    if not game_id or "/" in game_id or game_id.startswith("."):
        raise ValueError(f"bad game id {game_id!r}")
    return f"{game_id}.jsonl.gz"


class LocalStorage:
    def __init__(self, directory: Path) -> None:
        self.dir = directory

    def path(self, game_id: str) -> Path:
        return self.dir / _name(game_id)

    def put(self, game_id: str, data: bytes) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path(game_id).with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(self.path(game_id))

    def get(self, game_id: str) -> bytes:
        return self.path(game_id).read_bytes()  # FileNotFoundError when missing

    def presigned_url(self, game_id: str) -> str | None:
        return None  # served by the API's download endpoint

    def location(self, game_id: str) -> str:
        return str(self.path(game_id))


class S3Storage:
    def __init__(self, client: Any, bucket: str, prefix: str = "replays/",
                 signer: Any | None = None) -> None:
        self.s3 = client
        self.signer = signer or client  # signs download links for the address browsers use
        self.bucket = bucket
        self.prefix = prefix
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except Exception:
            self.s3.create_bucket(Bucket=self.bucket)
            log.info("created bucket %s", self.bucket)

    def key(self, game_id: str) -> str:
        return self.prefix + _name(game_id)

    def put(self, game_id: str, data: bytes) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=self.key(game_id), Body=data,
                           ContentType="application/gzip")

    def get(self, game_id: str) -> bytes:
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=self.key(game_id))
        except self.s3.exceptions.NoSuchKey as e:
            raise FileNotFoundError(self.key(game_id)) from e
        body: bytes = obj["Body"].read()
        return body

    def presigned_url(self, game_id: str) -> str | None:
        url: str = self.signer.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": self.key(game_id)},
            ExpiresIn=PRESIGN_SECONDS)
        return url

    def location(self, game_id: str) -> str:
        return f"s3://{self.bucket}/{self.key(game_id)}"


@lru_cache
def get_storage() -> ReplayStorage:
    s = get_settings()
    if s.s3_endpoint and s.s3_bucket:
        import boto3

        def client(endpoint: str) -> Any:
            return boto3.client(
                "s3", endpoint_url=endpoint, aws_access_key_id=s.s3_access_key,
                aws_secret_access_key=s.s3_secret_key, region_name="us-east-1")

        log.info("replays in S3 bucket %s at %s", s.s3_bucket, s.s3_endpoint)
        signer = client(s.s3_public_endpoint) if s.s3_public_endpoint else None
        return S3Storage(client(s.s3_endpoint), s.s3_bucket, signer=signer)
    return LocalStorage(s.replay_dir)
