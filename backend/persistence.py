"""Persist finished hands: game row, event rows and a gzipped .jsonl replay."""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import Game, GameEvent
from backend.storage import get_storage
from engine.game import GameState


def replay_path(game_id: str) -> Path:
    """Local file location (only meaningful with the default local storage)."""
    return get_settings().replay_dir / f"{game_id}.jsonl.gz"


def write_replay(s: GameState, meta: dict[str, Any]) -> str:
    lines = [json.dumps({"type": "META", **meta}, ensure_ascii=False)]
    lines += [json.dumps(ev, ensure_ascii=False) for ev in s.events]
    storage = get_storage()
    storage.put(s.game_id, gzip.compress(("\n".join(lines) + "\n").encode("utf-8")))
    return storage.location(s.game_id)


def read_replay(game_id: str) -> list[dict[str, Any]]:
    text = gzip.decompress(get_storage().get(game_id)).decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def result_row(s: GameState, duration_s: float | None = None) -> dict[str, Any]:
    """games.result (SPEC 08): the engine result plus total tai, scores after the hand and
    how long it took. The replay header keeps the bare engine result for verification."""
    assert s.result is not None
    r = s.result
    tai = sum(i["tai"] for i in r.get("tai_breakdown") or []) + (r.get("dealer_tai") or 0) \
        if r.get("kind") == "HU" else 0
    return {**r, "tai": tai, "final_scores": list(s.scores),
            "duration_s": None if duration_s is None else round(duration_s, 1)}


def save_hand(
    db: Session,
    s: GameState,
    *,
    room_id: str | None,
    hand_index: int,
    seats: list[dict[str, Any]],
    decisions: dict[int, dict[str, Any]] | None = None,
    actions: list[list[int]] | None = None,
    is_public: bool = False,
    scenario: dict[str, int] | None = None,
    duration_s: float | None = None,
) -> Game:
    """Store a finished hand. `decisions` maps event seq → AI decision details."""
    assert s.result is not None
    decisions = decisions or {}
    events = [
        {**ev, "ai_decision": decisions[ev["seq"]]} if ev["seq"] in decisions else ev
        for ev in s.events
    ]
    meta = {
        "game_id": s.game_id, "seed": s.seed, "dealer": s.dealer,
        "dealer_streak": s.dealer_streak, "round_wind": s.round_wind,
        "seats": seats, "result": s.result, "actions": actions or [],
        # practice hands start from a self-play position, not a fresh deal
        **({"scenario": dict(scenario)} if scenario else {}),
        "rules": {"base_points": s.rules.base_points, "tai_points": s.rules.tai_points,
                  "tai_cap": s.rules.tai_cap},
        "scores_before": [s.scores[i] - (s.result.get("payments") or [0] * 4)[i]
                          for i in range(4)],
    }
    snapshot = GameState(**{**s.__dict__, "events": events})
    location = write_replay(snapshot, meta)
    game = Game(
        id=s.game_id,
        room_id=room_id,
        round_wind=s.round_wind,
        dealer_seq=hand_index,
        dealer_streak=s.dealer_streak,
        seed=str(s.seed),
        seats=seats,
        result=result_row(s, duration_s),
        replay_url=location,
        is_public=is_public,
    )
    db.add(game)
    now = time.time()
    for ev in events:
        db.add(GameEvent(
            game_id=s.game_id,
            seq=ev["seq"],
            event_type=ev["type"],
            player=ev.get("player"),
            tile=ev.get("tile"),
            payload={k: v for k, v in ev.items() if k not in ("seq", "type", "player", "tile")},
            ts=ev.get("ts", now),
        ))
    db.commit()
    return game
