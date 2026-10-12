"""Prometheus metrics in the plain text exposition format (SPEC 12: monitoring).

Exposed at GET /metrics; set METRICS_TOKEN to require `Authorization: Bearer <token>`.
Hands per hour is `rate(maijong_hands_total[1h]) * 3600` on the Prometheus side.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

log = logging.getLogger("maijong.metrics")


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started = time.time()
        self.hands: dict[str, int] = {}
        self.matches = 0
        self.ws_open = 0

    def hand_finished(self, kind: str) -> None:
        with self._lock:
            self.hands[kind] = self.hands.get(kind, 0) + 1

    def match_finished(self) -> None:
        with self._lock:
            self.matches += 1

    def ws_connected(self) -> None:
        with self._lock:
            self.ws_open += 1

    def ws_disconnected(self) -> None:
        with self._lock:
            self.ws_open = max(0, self.ws_open - 1)


METRICS = Metrics()


def celery_queue_depth() -> int | None:
    """Pending tasks in the default Celery queue when the broker is Redis."""
    url = os.environ.get("CELERY_BROKER_URL", "")
    if not url.startswith(("redis://", "rediss://")):
        return None
    try:
        import redis

        return int(redis.Redis.from_url(url, socket_timeout=1).llen("celery"))
    except Exception:  # monitoring must never break the endpoint
        log.warning("could not read the Celery queue depth", exc_info=True)
        return None


def render(rooms: Any) -> str:
    m = METRICS
    lines = [
        "# HELP maijong_hands_total Finished hands by outcome.",
        "# TYPE maijong_hands_total counter",
    ]
    with m._lock:
        hands = dict(m.hands) or {"HU": 0}
        matches, ws_open = m.matches, m.ws_open
    lines += [f'maijong_hands_total{{kind="{k}"}} {v}' for k, v in sorted(hands.items())]
    live = list(getattr(rooms, "rooms", {}).values())
    in_game = sum(1 for r in live if getattr(r, "status", "") in ("IN_GAME", "ROUND_END"))
    lines += [
        "# HELP maijong_matches_total Finished matches.",
        "# TYPE maijong_matches_total counter",
        f"maijong_matches_total {matches}",
        "# HELP maijong_ws_connections Open game WebSocket connections.",
        "# TYPE maijong_ws_connections gauge",
        f"maijong_ws_connections {ws_open}",
        "# HELP maijong_rooms Rooms held by this instance, and how many are mid-game.",
        "# TYPE maijong_rooms gauge",
        f'maijong_rooms{{state="all"}} {len(live)}',
        f'maijong_rooms{{state="playing"}} {in_game}',
        "# HELP maijong_uptime_seconds Seconds since the process started.",
        "# TYPE maijong_uptime_seconds gauge",
        f"maijong_uptime_seconds {time.time() - m.started:.0f}",
    ]
    depth = celery_queue_depth()
    if depth is not None:
        lines += [
            "# HELP maijong_celery_queue_depth Tasks waiting in the Celery queue.",
            "# TYPE maijong_celery_queue_depth gauge",
            f"maijong_celery_queue_depth {depth}",
        ]
    return "\n".join(lines) + "\n"
