"""Opt-in WebSocket message batching (SPEC P11-7).

A client connecting with ?batch=1 gets every message produced while the room handles one
event (an action plus the bot responses that follow before the next pause) in a single
frame: {"type": "BATCH", "payload": {"messages": [...]}}. Within a batch only the newest
STATE_UPDATE is kept, since each one is a complete snapshot.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

log = logging.getLogger("maijong.ws")


class _Sender(Protocol):
    async def send_json(self, data: Any) -> None: ...


def coalesce(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    last_state = max((i for i, m in enumerate(messages) if m.get("type") == "STATE_UPDATE"),
                     default=-1)
    return [m for i, m in enumerate(messages)
            if m.get("type") != "STATE_UPDATE" or i == last_state]


class BatchingSocket:
    def __init__(self, ws: _Sender) -> None:
        self.ws = ws
        self._queue: list[dict[str, Any]] = []
        self._flushing: asyncio.Task[None] | None = None
        self.frames = 0  # frames actually written (for tests and metrics)

    async def send_json(self, data: Any) -> None:
        self._queue.append(data)
        if self._flushing is None or self._flushing.done():
            self._flushing = asyncio.get_running_loop().create_task(self._flush())

    async def _flush(self) -> None:
        await asyncio.sleep(0)  # let the current handler finish queuing
        while self._queue:  # messages queued while a frame was being written go next
            batch, self._queue = coalesce(self._queue), []
            frame = batch[0] if len(batch) == 1 else {"type": "BATCH",
                                                      "payload": {"messages": batch}}
            try:
                await self.ws.send_json(frame)
                self.frames += 1
            except Exception:  # closed socket; the receive loop handles the disconnect
                log.debug("batched send failed", exc_info=True)
                self._queue = []

    async def drain(self) -> None:
        """Wait until everything queued so far has been written."""
        while self._flushing is not None and not self._flushing.done():
            await self._flushing
