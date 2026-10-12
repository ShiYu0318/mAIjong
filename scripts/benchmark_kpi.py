"""Measure the launch KPIs from SPEC 1.2 that have a hard number.

- Broadcast latency: an in-process server plays full matches (bot delay 0) while one seat
  answers every request; we time each ACTION we send until the server's next message
  (the STATE_UPDATE carrying it). Claim responses (PASS/CHI/PON/KONG/HU on another
  player's discard) are the "叫牌廣播" figure; target P95 <= 100 ms.
- Lv5 response time: the Lv5 agent decides every turn of several self-play hands;
  target <= 2 s per decision.

Example:
    uv run python scripts/benchmark_kpi.py --matches 2 --hands 4
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CLAIMS = {"PASS", "CHI_LOW", "CHI_MID", "CHI_HIGH", "PON", "KONG", "HU"}


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def summary(name: str, ms: list[float], target: float | None = None) -> str:
    if not ms:
        return f"{name:<28} (no samples)"
    p95 = pct(ms, 0.95)
    verdict = "" if target is None else ("  OK" if p95 <= target else f"  OVER {target:.0f} ms")
    return (f"{name:<28} n={len(ms):<5} p50={statistics.median(ms):7.1f} ms  "
            f"p95={p95:7.1f} ms  max={max(ms):7.1f} ms{verdict}")


def broadcast_latency(matches: int) -> tuple[list[float], list[float]]:
    tmp = Path(tempfile.mkdtemp(prefix="maijong-bench-"))
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{tmp / 'bench.db'}", "REPLAY_DIR": str(tmp / "replays"),
        "SECRET_KEY": "benchmark-secret-key-that-is-long-enough",
        "RATE_LIMIT_API_PER_MIN": "100000", "RATE_LIMIT_WS_PER_SEC": "100000",
    })
    from fastapi.testclient import TestClient

    from backend.main import create_app

    claim_ms: list[float] = []
    turn_ms: list[float] = []
    with TestClient(create_app()) as client:
        token = client.post("/api/v1/auth/guest").json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        for _ in range(matches):
            config = {"time_limit": None, "rounds": 1, "bot_delay": 0, "next_hand_delay": 0,
                      "bot_levels": [None, 3, 3, 3]}
            room = client.post("/api/v1/rooms", headers=headers,
                               json={"type": "PRIVATE", "config": config}).json()
            rid = room["room_id"]
            j = client.post(f"/api/v1/rooms/{rid}/join", json={}, headers=headers).json()
            seat = j["seat"]
            with client.websocket_connect(f"/ws/game/{rid}?token={j['ws_token']}") as ws:
                ws.receive_json()
                client.post(f"/api/v1/rooms/{rid}/start", headers=headers)
                sent_at: float | None = None
                sent_claim = False
                while True:
                    msg = ws.receive_json()
                    if sent_at is not None:
                        elapsed = (time.perf_counter() - sent_at) * 1000
                        (claim_ms if sent_claim else turn_ms).append(elapsed)
                        sent_at = None
                    if msg["type"] == "GAME_END":
                        break
                    if msg["type"] == "ACTION_REQUEST" and msg["payload"]["player"] == seat:
                        legal = msg["payload"]["legal_actions"]
                        pick = next((a for a in legal if a["action_type"] == "HU"), None) \
                            or next((a for a in legal if a["action_type"] == "PASS"), None) \
                            or legal[-1]
                        sent_claim = any(a["action_type"] == "PASS" for a in legal) \
                            and pick["action_type"] in CLAIMS
                        sent_at = time.perf_counter()
                        ws.send_json({"type": "ACTION", "payload": pick})
    return claim_ms, turn_ms


def lv5_decision(hands: int) -> tuple[str, list[float]]:
    from ai.agents import create_agent
    from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game

    lv5 = create_agent(5, seed=0)
    agents = [lv5, create_agent(3, 1), create_agent(3, 2), create_agent(3, 3)]
    ms: list[float] = []
    for h in range(hands):
        s = new_game(seed=1000 + h)
        while s.phase is not Phase.ENDED:
            p = acting_players(s)[0]
            legal = get_legal_actions(s, p)
            t0 = time.perf_counter()
            a = agents[p].act(s, p, legal)
            if p == 0:
                ms.append((time.perf_counter() - t0) * 1000)
            s, _ = apply_action(s, p, a)
    return type(lv5).__name__, ms


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--matches", type=int, default=2, help="online matches for the latency test")
    ap.add_argument("--hands", type=int, default=4, help="self-play hands for the Lv5 timing")
    args = ap.parse_args()

    claim_ms, turn_ms = broadcast_latency(args.matches)
    print(summary("claim -> broadcast", claim_ms, 100))
    print(summary("turn -> broadcast", turn_ms, 100))
    name, ms = lv5_decision(args.hands)
    print(summary(f"Lv5 decision ({name})", ms, 2000))


if __name__ == "__main__":
    main()
