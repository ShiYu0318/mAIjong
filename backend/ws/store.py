"""Room state in Redis (SPEC P2-3): snapshots for crash recovery and pub/sub fan-out.

Without REDIS_URL a NullStore keeps the original single-process, in-memory behaviour.

Keys (prefix `maijong:`):
  room:{id}        JSON snapshot: config, seats, match, hand seed and the hand's actions
  room:{id}:view   latest spectator view (STATE_UPDATE payload without concealed tiles)
  room:{id}:events pub/sub channel carrying every spectator-visible message
  rooms:{instance} set of room ids owned by one backend instance

Seated players must reach the instance that owns their room (route by room id, e.g. a
sticky load-balancer rule); spectators can connect to any instance and are relayed the
owner's messages through the channel.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol

log = logging.getLogger("maijong.store")
PREFIX = "maijong:"
SNAPSHOT_TTL = 24 * 3600  # an idle room disappears after a day


class RoomStore(Protocol):
    instance: str

    async def save(self, room_id: str, snapshot: dict[str, Any]) -> None: ...
    async def delete(self, room_id: str) -> None: ...
    async def load_owned(self) -> list[dict[str, Any]]: ...
    async def load(self, room_id: str) -> dict[str, Any] | None: ...
    async def publish(self, room_id: str, message: dict[str, Any]) -> None: ...
    async def set_view(self, room_id: str, view: dict[str, Any]) -> None: ...
    async def get_view(self, room_id: str) -> dict[str, Any] | None: ...
    def subscribe(self, room_id: str) -> AsyncIterator[dict[str, Any]]: ...
    async def close(self) -> None: ...


class NullStore:
    """Single-process default: nothing is persisted or relayed."""

    instance = "local"

    async def save(self, room_id: str, snapshot: dict[str, Any]) -> None:
        return None

    async def delete(self, room_id: str) -> None:
        return None

    async def load_owned(self) -> list[dict[str, Any]]:
        return []

    async def load(self, room_id: str) -> dict[str, Any] | None:
        return None

    async def publish(self, room_id: str, message: dict[str, Any]) -> None:
        return None

    async def set_view(self, room_id: str, view: dict[str, Any]) -> None:
        return None

    async def get_view(self, room_id: str) -> dict[str, Any] | None:
        return None

    async def subscribe(self, room_id: str) -> AsyncIterator[dict[str, Any]]:
        return
        yield  # pragma: no cover - makes this an (empty) async generator

    async def close(self) -> None:
        return None


class RedisStore:
    def __init__(self, client: Any, instance: str = "default") -> None:
        self.r = client
        self.instance = instance

    @classmethod
    def from_url(cls, url: str, instance: str = "default") -> RedisStore:
        import redis.asyncio as redis

        return cls(redis.Redis.from_url(url, decode_responses=True), instance)

    def _key(self, room_id: str, suffix: str = "") -> str:
        return f"{PREFIX}room:{room_id}{suffix}"

    async def save(self, room_id: str, snapshot: dict[str, Any]) -> None:
        data = json.dumps({**snapshot, "owner": self.instance}, ensure_ascii=False)
        async with self.r.pipeline(transaction=True) as p:
            p.set(self._key(room_id), data, ex=SNAPSHOT_TTL)
            p.sadd(f"{PREFIX}rooms:{self.instance}", room_id)
            await p.execute()

    async def delete(self, room_id: str) -> None:
        async with self.r.pipeline(transaction=True) as p:
            p.delete(self._key(room_id), self._key(room_id, ":view"))
            p.srem(f"{PREFIX}rooms:{self.instance}", room_id)
            await p.execute()

    async def load(self, room_id: str) -> dict[str, Any] | None:
        raw = await self.r.get(self._key(room_id))
        if raw is None:
            return None
        data: dict[str, Any] = json.loads(raw)
        return data

    async def load_owned(self) -> list[dict[str, Any]]:
        out = []
        for room_id in sorted(await self.r.smembers(f"{PREFIX}rooms:{self.instance}")):
            snap = await self.load(room_id)
            if snap is None:  # expired: drop it from the index
                await self.r.srem(f"{PREFIX}rooms:{self.instance}", room_id)
            else:
                out.append(snap)
        return out

    async def publish(self, room_id: str, message: dict[str, Any]) -> None:
        await self.r.publish(self._key(room_id, ":events"), json.dumps(message, ensure_ascii=False))

    async def set_view(self, room_id: str, view: dict[str, Any]) -> None:
        await self.r.set(self._key(room_id, ":view"), json.dumps(view, ensure_ascii=False),
                         ex=SNAPSHOT_TTL)

    async def get_view(self, room_id: str) -> dict[str, Any] | None:
        raw = await self.r.get(self._key(room_id, ":view"))
        if raw is None:
            return None
        data: dict[str, Any] = json.loads(raw)
        return data

    async def subscribe(self, room_id: str) -> AsyncIterator[dict[str, Any]]:
        pubsub = self.r.pubsub()
        await pubsub.subscribe(self._key(room_id, ":events"))
        try:
            async for item in pubsub.listen():
                if item.get("type") == "message":
                    yield json.loads(item["data"])
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()

    async def close(self) -> None:
        await self.r.aclose()


def store_from_settings() -> RoomStore:
    import os

    from backend.config import get_settings

    url = get_settings().redis_url
    if not url:
        return NullStore()
    instance = os.environ.get("INSTANCE_ID", "default")
    log.info("room state in Redis (instance %s)", instance)
    return RedisStore.from_url(url, instance)
