"""Load test (SPEC 11): many concurrent WebSocket tables against a running server.

Each table gets its own guest account, one scripted player and three Lv3 bots, and plays
until its first hand ends. Every action the player sends is timed until the server's next
message; the target is p95 < 200 ms. Start the server with relaxed rate limits, e.g.

    RATE_LIMIT_AUTH_PER_MIN=100000 RATE_LIMIT_API_PER_MIN=100000 \\
        uv run uvicorn backend.main:app --port 8030
    uv run python scripts/load_test.py --url http://localhost:8030 --rooms 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time

import httpx
import websockets


async def table(client: httpx.AsyncClient, ws_base: str, bot_delay: float,
                latencies: list[float]) -> int:
    """Play one table to the end of its first hand; returns the number of timed actions."""
    token = (await client.post("/api/v1/auth/guest")).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    cfg = {"time_limit": 30, "rounds": 1, "bot_delay": bot_delay, "next_hand_delay": 0,
           "bot_levels": [None, 3, 3, 3]}
    room = (await client.post("/api/v1/rooms", headers=h,
                              json={"type": "PRIVATE", "config": cfg})).json()
    rid = room["room_id"]
    j = (await client.post(f"/api/v1/rooms/{rid}/join", headers=h, json={})).json()
    seat, timed = j["seat"], 0
    async with websockets.connect(f"{ws_base}/ws/game/{rid}?token={j['ws_token']}",
                                  max_size=2**22) as ws:
        await ws.recv()
        (await client.post(f"/api/v1/rooms/{rid}/start", headers=h)).raise_for_status()
        sent: float | None = None
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            if sent is not None:
                latencies.append((time.perf_counter() - sent) * 1000)
                sent, timed = None, timed + 1
            if msg["type"] in ("WIN_DECLARED", "ROUND_DRAW", "GAME_END"):
                return timed
            p = msg.get("payload") or {}
            if msg["type"] == "ACTION_REQUEST" and p.get("player") == seat:
                legal = p["legal_actions"]
                pick = next((a for a in legal if a["action_type"] == "HU"), None) \
                    or next((a for a in legal if a["action_type"] == "PASS"), None) or legal[-1]
                sent = time.perf_counter()
                await ws.send(json.dumps({"type": "ACTION", "payload": pick}))


async def run(url: str, rooms: int, bot_delay: float) -> tuple[list[float], int, float]:
    ws_base = url.replace("http", "ws", 1)
    latencies: list[float] = []
    limits = httpx.Limits(max_connections=rooms + 10)
    async with httpx.AsyncClient(base_url=url, timeout=30, limits=limits) as client:
        t0 = time.perf_counter()
        results = await asyncio.gather(*(table(client, ws_base, bot_delay, latencies)
                                         for _ in range(rooms)), return_exceptions=True)
        elapsed = time.perf_counter() - t0
    failures = [r for r in results if isinstance(r, BaseException)]
    for f in failures[:5]:
        print(f"table failed: {f!r}", file=sys.stderr)
    return latencies, len(failures), elapsed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8030")
    ap.add_argument("--rooms", type=int, default=100)
    ap.add_argument("--bot-delay", type=float, default=0.6, help="seconds per bot move (as live)")
    ap.add_argument("--target-ms", type=float, default=200)
    args = ap.parse_args()
    lat, failed, elapsed = asyncio.run(run(args.url, args.rooms, args.bot_delay))
    if not lat:
        print("no actions were timed")
        return 1
    lat.sort()
    p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))]
    print(f"{args.rooms} tables ({failed} failed) in {elapsed:.0f}s, {len(lat)} timed actions")
    print(f"action -> next message: p50 {statistics.median(lat):.1f} ms, p95 {p95:.1f} ms, "
          f"max {lat[-1]:.1f} ms (target p95 < {args.target_ms:.0f} ms)")
    ok = failed == 0 and p95 < args.target_ms
    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
