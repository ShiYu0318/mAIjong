"""Finished games, replays and annotations (SPEC 04.8, 09.1).

Replays are capability links: anyone with the game id can watch it. The public flag
only controls listing in the replay explorer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.deps import SessionDep, UserDep
from backend.models import Game, ReplayAnnotation, User
from backend.persistence import read_replay, replay_path
from backend.replay import ReplayError, build_frames

router = APIRouter(tags=["games"])


def _game(db: SessionDep, game_id: str) -> Game:
    g = db.get(Game, game_id)
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "game not found")
    return g


def game_out(g: Game) -> dict[str, Any]:
    return {
        "id": g.id, "room_id": g.room_id, "round_wind": g.round_wind,
        "hand_index": g.dealer_seq, "dealer_streak": g.dealer_streak, "seats": g.seats,
        "result": g.result, "is_public": g.is_public, "created_at": g.created_at.isoformat(),
    }


@router.get("/games/{game_id}")
def get_game(game_id: str, db: SessionDep) -> dict[str, Any]:
    return game_out(_game(db, game_id))


@router.get("/games/{game_id}/replay")
def replay_url(game_id: str, db: SessionDep, request: Request) -> dict[str, str]:
    _game(db, game_id)
    url = str(request.url_for("download_replay", game_id=game_id))
    return {"url": url}


@router.get("/games/{game_id}/replay/download", name="download_replay")
def download_replay(game_id: str, db: SessionDep) -> FileResponse:
    _game(db, game_id)
    path = replay_path(game_id)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "replay file missing")
    return FileResponse(path, media_type="application/gzip", filename=f"{game_id}.jsonl.gz")


@router.get("/games/{game_id}/frames")
def frames(game_id: str, db: SessionDep) -> dict[str, Any]:
    g = _game(db, game_id)
    try:
        data = build_frames(read_replay(game_id))
    except (FileNotFoundError, ReplayError) as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"replay unavailable: {e}") from e
    data["game"] = game_out(g)
    return data


@router.get("/users/{user_id}/games")
def user_games(user_id: str, db: SessionDep, page: int = 1, limit: int = 20
               ) -> list[dict[str, Any]]:
    limit = max(1, min(100, limit))
    rows = db.scalars(select(Game).order_by(Game.created_at.desc()).limit(2000)).all()
    mine = [g for g in rows if any(s and s.get("user_id") == user_id for s in g.seats)]
    start = (max(1, page) - 1) * limit
    return [game_out(g) for g in mine[start:start + limit]]


class AnnotationIn(BaseModel):
    seq: int = Field(ge=0)
    note: str = Field(min_length=1, max_length=500)


@router.get("/games/{game_id}/annotations")
def list_annotations(game_id: str, db: SessionDep) -> list[dict[str, Any]]:
    _game(db, game_id)
    rows = db.scalars(select(ReplayAnnotation).where(ReplayAnnotation.game_id == game_id)
                      .order_by(ReplayAnnotation.seq)).all()
    names = {u.id: u.username for u in db.scalars(
        select(User).where(User.id.in_({r.user_id for r in rows}))).all()} if rows else {}
    return [{"id": r.id, "seq": r.seq, "note": r.note, "user": names.get(r.user_id, ""),
             "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/games/{game_id}/annotations", status_code=status.HTTP_201_CREATED)
def add_annotation(game_id: str, body: AnnotationIn, db: SessionDep, user: UserDep
                   ) -> dict[str, Any]:
    _game(db, game_id)
    row = ReplayAnnotation(game_id=game_id, user_id=user.id, seq=body.seq, note=body.note)
    db.add(row)
    db.commit()
    return {"id": row.id, "seq": row.seq, "note": row.note, "user": user.username}
