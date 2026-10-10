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
from engine.game import GameState


def replay_path(game_id: str) -> Path:
    return get_settings().replay_dir / f"{game_id}.jsonl.gz"


def write_replay(s: GameState, meta: dict[str, Any]) -> Path:
    path = replay_path(s.game_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"type": "META", **meta}, ensure_ascii=False) + "\n")
        for ev in s.events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return path


def read_replay(game_id: str) -> list[dict[str, Any]]:
    path = replay_path(game_id)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


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
        "rules": {"base_points": s.rules.base_points, "tai_points": s.rules.tai_points,
                  "tai_cap": s.rules.tai_cap},
        "scores_before": [s.scores[i] - (s.result.get("payments") or [0] * 4)[i]
                          for i in range(4)],
    }
    snapshot = GameState(**{**s.__dict__, "events": events})
    path = write_replay(snapshot, meta)
    game = Game(
        id=s.game_id,
        room_id=room_id,
        round_wind=s.round_wind,
        dealer_seq=hand_index,
        dealer_streak=s.dealer_streak,
        seed=str(s.seed),
        seats=seats,
        result=s.result,
        replay_url=str(path),
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
