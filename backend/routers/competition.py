"""Leaderboards, seasons, challenges and the arena (SPEC 07, 09.1)."""

from __future__ import annotations

import os
import random
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.arena import ensure_house_agents, play_match, run_arena_match
from backend.db import session_factory
from backend.deps import SessionDep, UserDep
from backend.models import Agent, Challenge, EloHistory, Season, User, new_id
from backend.security import create_ws_token
from backend.ws.hub import RoomConfig, RoomManager

router = APIRouter(tags=["competition"])
SEASON_LENGTH = timedelta(weeks=4)


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def current_season(db: Session) -> Season:
    s = db.scalar(select(Season).where(Season.status == "ACTIVE").order_by(Season.id.desc()))
    if s is None:
        start = datetime.now(UTC)
        s = Season(starts_at=start, ends_at=start + SEASON_LENGTH, status="ACTIVE")
        db.add(s)
        db.commit()
    return s


def season_out(s: Season) -> dict[str, Any]:
    return {"id": s.id, "starts_at": _utc(s.starts_at).isoformat(),
            "ends_at": _utc(s.ends_at).isoformat(), "status": s.status,
            "final_ranking": s.final_ranking}


def _placements(db: Session, since: datetime, agent: bool) -> dict[str, list[int]]:
    col = EloHistory.agent_id if agent else EloHistory.user_id
    rows = db.execute(select(col, EloHistory.placement).where(
        col.is_not(None), EloHistory.recorded_at >= since)).all()
    out: dict[str, list[int]] = {}
    for key, place in rows:
        if key is not None:
            out.setdefault(key, []).append(place)
    return out


def leaderboard_rows(db: Session, season: Season, kind: str = "agent") -> list[dict[str, Any]]:
    since = _utc(season.starts_at).replace(tzinfo=None)
    places = _placements(db, since, kind == "agent")
    rows: list[dict[str, Any]] = []
    if kind == "agent":
        owners = {u.id: u.username for u in db.scalars(select(User)).all()}
        for a in db.scalars(select(Agent).where(Agent.status == "ACTIVE")).all():
            p = places.get(a.id, [])
            rows.append({"id": a.id, "name": a.name, "version": a.version,
                         "author": owners.get(a.owner_id or "", "官方"), "elo": round(a.elo, 1),
                         "games": len(p), "first_rate": p.count(1) / len(p) if p else 0.0,
                         "avg_place": sum(p) / len(p) if p else None})
    else:
        for u in db.scalars(select(User)).all():
            p = places.get(u.id, [])
            if not p:
                continue
            rows.append({"id": u.id, "name": u.username, "author": u.username,
                         "elo": round(u.elo_human, 1), "games": len(p),
                         "first_rate": p.count(1) / len(p), "avg_place": sum(p) / len(p)})
    rows.sort(key=lambda r: -r["elo"])
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


@router.get("/leaderboard")
def leaderboard(db: SessionDep, season: str = "current", kind: str = "agent"
                ) -> dict[str, Any]:
    ensure_house_agents(db)
    if season == "current":
        s = current_season(db)
        return {"season": season_out(s), "rows": leaderboard_rows(db, s, kind)}
    past = db.get(Season, int(season))
    if past is None:
        raise HTTPException(404, "season not found")
    key = "agents" if kind == "agent" else "humans"
    return {"season": season_out(past), "rows": (past.final_ranking or {}).get(key, [])}


@router.get("/seasons")
def seasons(db: SessionDep) -> list[dict[str, Any]]:
    current_season(db)
    return [season_out(s) for s in db.scalars(select(Season).order_by(Season.id.desc())).all()]


@router.get("/seasons/{season_id}")
def season(season_id: int, db: SessionDep) -> dict[str, Any]:
    s = db.get(Season, season_id)
    if s is None:
        raise HTTPException(404, "season not found")
    return season_out(s)


def _require_admin(token: str | None) -> None:
    expected = os.environ.get("ADMIN_TOKEN")
    if not expected or token != expected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin token required")


@router.post("/seasons/rollover")
def rollover(db: SessionDep, x_admin_token: str | None = Header(default=None)
             ) -> dict[str, Any]:
    """End the current season: snapshot rankings, award badges to the top three and
    soft-reset every rating halfway back to 1500 (P10-4)."""
    _require_admin(x_admin_token)
    s = current_season(db)
    agents = leaderboard_rows(db, s, "agent")
    humans = leaderboard_rows(db, s, "human")
    s.final_ranking = {"agents": agents, "humans": humans,
                       "badges": [r["id"] for r in agents[:3]]}
    s.status = "FINISHED"
    s.ends_at = datetime.now(UTC)
    for a in db.scalars(select(Agent)).all():
        a.elo = 1500 + (a.elo - 1500) * 0.5
    for u in db.scalars(select(User)).all():
        u.elo_human = 1500 + (u.elo_human - 1500) * 0.5
    db.commit()
    return {"finished": season_out(s), "current": season_out(current_season(db))}


# ---------------------------------------------------------------- challenges


class ChallengeIn(BaseModel):
    agent_id: str
    opponent_id: str
    n_games: int = Field(10, ge=1, le=50)


def challenge_out(c: Challenge) -> dict[str, Any]:
    return {"id": c.id, "agent_id": c.agent_id, "opponent_id": c.opponent_id,
            "n_games": c.n_games, "status": c.status, "result": c.result,
            "created_at": c.created_at.isoformat()}


def _run_challenge(challenge_id: str) -> None:
    with session_factory()() as db:
        c = db.get(Challenge, challenge_id)
        if c is None:
            return
        c.status = "RUNNING"
        db.commit()
        try:
            house = ensure_house_agents(db)[:2]
            a, b = db.get(Agent, c.agent_id), db.get(Agent, c.opponent_id)
            assert a is not None and b is not None
            totals = {a.id: 0, b.id: 0}
            firsts = {a.id: 0, b.id: 0}
            for k in range(c.n_games):
                order = [a, b, *house]
                shift = k % 4
                seats = order[shift:] + order[:shift]
                scores, _, _ = play_match(seats, seed=k * 7919 + 1)
                from engine.match import ranks

                rk = ranks(scores)
                for i, ag in enumerate(seats):
                    if ag.id in totals:
                        totals[ag.id] += scores[i]
                        firsts[ag.id] += int(rk[i] == 1)
            c.result = {"total_score": totals, "first_places": firsts,
                        "winner": max(totals, key=lambda x: totals[x])}
            c.status = "DONE"
        except Exception as e:
            c.status = "FAILED"
            c.result = {"error": str(e)}
        db.commit()


@router.post("/challenges", status_code=status.HTTP_202_ACCEPTED)
def create_challenge(body: ChallengeIn, db: SessionDep, user: UserDep) -> dict[str, Any]:
    for aid in (body.agent_id, body.opponent_id):
        ag = db.get(Agent, aid)
        if ag is None or ag.status != "ACTIVE":
            raise HTTPException(422, f"agent {aid} is not active")
    c = Challenge(challenger_id=user.id, agent_id=body.agent_id, opponent_id=body.opponent_id,
                  n_games=body.n_games)
    db.add(c)
    db.commit()
    threading.Thread(target=_run_challenge, args=(c.id,), daemon=True).start()
    return challenge_out(c)


@router.get("/challenges/{challenge_id}")
def get_challenge(challenge_id: str, db: SessionDep) -> dict[str, Any]:
    c = db.get(Challenge, challenge_id)
    if c is None:
        raise HTTPException(404, "challenge not found")
    return challenge_out(c)


# ---------------------------------------------------------------- arena


@router.post("/arena/run")
def arena_run(db: SessionDep, x_admin_token: str | None = Header(default=None)
              ) -> dict[str, Any]:
    """Play one rated arena match now (the background scheduler does this periodically)."""
    _require_admin(x_admin_token)
    res = run_arena_match(db)
    if res is None:
        raise HTTPException(409, "not enough eligible agents")
    return res


@router.post("/arena/human/join")
async def arena_human_join(request: Request, db: SessionDep, user: UserDep) -> dict[str, Any]:
    """Human vs agents (P10-6): three opponents near the player's rating; only the human
    rating changes."""
    ensure_house_agents(db)
    pool = db.scalars(select(Agent).where(Agent.status == "ACTIVE")).all()
    opponents = sorted(pool, key=lambda a: (abs(a.elo - user.elo_human), random.random()))[:3]
    manager: RoomManager = request.app.state.rooms
    cfg = RoomConfig(time_limit=30, rounds=1, bot_levels=[None, 3, 3, 3])
    room = manager.create(new_id(), "ARENA", cfg, user.id)
    room.arena_agents = {i + 1: a.id for i, a in enumerate(opponents)}
    for i, a in enumerate(opponents, start=1):
        room.attach_agent(i, a)
    seat = room.join(user.id, user.username, 0)
    agent_ids = [a.id for a in opponents]
    room.match_end_hook = lambda r, scores: record_human_arena(r.id, user.id, seat, scores,
                                                                agent_ids)
    await room.start()
    return {"room": room.public(), "seat": seat,
            "ws_token": create_ws_token(room.id, seat, user.id, user.username)}



def record_human_arena(room_id: str, user_id: str, seat: int, scores: list[int],
                       agent_ids: list[str]) -> None:
    """Match-end hook for ARENA rooms: update only the human rating (SPEC 07.1 D)."""
    from ai.elo import update_elo
    from engine.match import ranks

    with session_factory()() as db:
        user = db.get(User, user_id)
        if user is None:
            return
        opp = [db.get(Agent, a) for a in agent_ids]
        ratings = [a.elo if a else 1500.0 for a in opp]
        ratings.insert(seat, user.elo_human)
        order = ranks(scores)
        played = [400] * 4
        played[seat] = user.games_played
        before = user.elo_human
        user.elo_human = update_elo(ratings, order, played)[seat]
        user.games_played += 1
        db.add(EloHistory(user_id=user.id, elo_before=before, elo_after=user.elo_human,
                          placement=order[seat]))
        db.commit()
