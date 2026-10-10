"""AI tutor: lessons progress, hand analysis and decision quizzes (SPEC 04.7)."""

from __future__ import annotations

import random
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ai.explainability.analysis import HandInput, analyze_hand, generate_quiz, load_quiz, quiz_view
from ai.explainability.candidate_scorer import score_all_discards
from backend.deps import OptionalUserDep, SessionDep, UserDep
from backend.hints.llm_provider import template_explain
from backend.models import TutorProgress, now
from backend.security import TokenError, create_quiz_token, decode_token
from engine.hand import Meld, MeldType

router = APIRouter(prefix="/tutor", tags=["tutor"])

LESSONS = [
    ("tiles", "認識牌張"), ("sets", "順子、刻子與將"), ("winning", "胡牌結構"),
    ("flowers", "花牌與補花"), ("calls", "吃、碰、槓"), ("tai", "台數怎麼算"),
    ("discard", "打牌基本功"), ("defense", "防守基礎"),
]


class MeldIn(BaseModel):
    type: MeldType
    tiles: list[int] = Field(min_length=3, max_length=4)


class AnalyzeIn(BaseModel):
    hand: list[int] = Field(min_length=1, max_length=17)
    melds: list[MeldIn] = Field(default_factory=list, max_length=5)
    flowers: list[int] = Field(default_factory=list, max_length=8)
    seat_wind: int = Field(0, ge=0, le=3)
    round_wind: int = Field(0, ge=0, le=3)


@router.get("/lessons")
def lessons() -> list[dict[str, str]]:
    return [{"id": i, "title": t} for i, t in LESSONS]


@router.post("/analyze")
def analyze(body: AnalyzeIn) -> dict[str, Any]:
    if any(not 0 <= t < 34 for t in body.hand) or any(not 34 <= f < 42 for f in body.flowers):
        raise HTTPException(422, "牌張編號不正確")
    melds = [Meld(m.type, tuple(m.tiles)) for m in body.melds]
    try:
        return analyze_hand(HandInput(body.hand, melds, body.flowers, body.seat_wind,
                                      body.round_wind))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/quiz")
def quiz(difficulty: int = 2) -> dict[str, Any]:
    q = generate_quiz(random.Random(), max(1, min(3, difficulty)))
    return {"quiz_token": create_quiz_token(q.seed, q.step, q.seat), "difficulty": difficulty,
            "position": quiz_view(q)}


class AnswerIn(BaseModel):
    quiz_token: str
    tile: int = Field(ge=0, le=33)


@router.post("/quiz/answer")
def answer(body: AnswerIn, db: SessionDep, user: OptionalUserDep) -> dict[str, Any]:
    try:
        claims = decode_token(body.quiz_token, "quiz")
    except TokenError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "題目已過期，請換一題") from e
    q = load_quiz(int(claims["seed"]), int(claims["step"]), int(claims["seat"]))
    cands = [c.to_dict() for c in score_all_discards(q.state, q.seat)]
    tiles_ok = {c["tile"] for c in cands}
    if body.tile not in tiles_ok:
        raise HTTPException(422, "這張牌不在手上")
    best = cands[0]
    rank = next(i for i, c in enumerate(cands) if c["tile"] == body.tile)
    mine = cands[rank]
    good = mine["shanten_after"] == best["shanten_after"] and \
        mine["uke_count"] >= 0.9 * best["uke_count"]
    verdict = "best" if rank == 0 else "good" if good else "worse"
    if user is not None:
        _record_quiz(db, user.id, verdict != "worse")
    return {
        "verdict": verdict, "rank": rank + 1, "best": best, "chosen": mine,
        "candidates": cands[:6], "explanation": template_explain(cands, body.tile),
    }


def _record_quiz(db: SessionDep, user_id: str, correct: bool) -> None:
    row = db.get(TutorProgress, (user_id, "quiz"))
    if row is None:
        row = TutorProgress(user_id=user_id, lesson_id="quiz", status="STARTED", quiz_score=0.5)
        db.add(row)
    prev = row.quiz_score if row.quiz_score is not None else 0.5
    row.quiz_score = round(prev * 0.8 + (1.0 if correct else 0.0) * 0.2, 4)  # moving success rate
    row.updated_at = now()
    db.commit()


class ProgressIn(BaseModel):
    status: str = Field(pattern="^(STARTED|COMPLETED)$")
    quiz_score: float | None = Field(None, ge=0, le=1)


@router.get("/progress")
def progress(db: SessionDep, user: UserDep) -> list[dict[str, Any]]:
    rows = db.scalars(select(TutorProgress).where(TutorProgress.user_id == user.id)).all()
    return [{"lesson_id": r.lesson_id, "status": r.status, "quiz_score": r.quiz_score}
            for r in rows]


@router.put("/progress/{lesson_id}")
def set_progress(lesson_id: str, body: ProgressIn, db: SessionDep, user: UserDep
                 ) -> dict[str, Any]:
    if lesson_id not in dict(LESSONS) and lesson_id != "quiz":
        raise HTTPException(404, "unknown lesson")
    row = db.get(TutorProgress, (user.id, lesson_id))
    if row is None:
        row = TutorProgress(user_id=user.id, lesson_id=lesson_id, status=body.status)
        db.add(row)
    row.status = body.status
    if body.quiz_score is not None:
        row.quiz_score = body.quiz_score
    row.updated_at = now()
    db.commit()
    return {"lesson_id": lesson_id, "status": row.status, "quiz_score": row.quiz_score}
