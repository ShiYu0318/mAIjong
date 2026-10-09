"""ORM models (SPEC [08]). Portable across PostgreSQL and SQLite."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(30), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    elo_human: Mapped[float] = mapped_column(Float, default=1500.0)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=now)


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str | None] = mapped_column(String(6), unique=True)
    type: Mapped[str] = mapped_column(String(20))  # QUICK|PRIVATE|PRACTICE|ARENA
    config: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="WAITING")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=now)


class Game(Base):
    __tablename__ = "games"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id"))
    round_wind: Mapped[int] = mapped_column(SmallInteger)
    dealer_seq: Mapped[int] = mapped_column(SmallInteger)
    dealer_streak: Mapped[int] = mapped_column(SmallInteger, default=0)
    seed: Mapped[str | None] = mapped_column(String(32))
    seats: Mapped[list[Any]] = mapped_column(default=list)
    result: Mapped[dict[str, Any]] = mapped_column(default=dict)
    replay_url: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=now)


class GameEvent(Base):
    __tablename__ = "game_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(20))
    player: Mapped[int | None] = mapped_column(SmallInteger)
    tile: Mapped[int | None] = mapped_column(SmallInteger)
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    ts: Mapped[float] = mapped_column(Float)


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    elo: Mapped[float] = mapped_column(Float, default=1500.0)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    submission_path: Mapped[str | None] = mapped_column(Text)
    model_sha256: Mapped[str | None] = mapped_column(String(64))
    manifest: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|ACTIVE|BANNED
    created_at: Mapped[datetime] = mapped_column(default=now)


class EloHistory(Base):
    __tablename__ = "elo_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    game_id: Mapped[str | None] = mapped_column(ForeignKey("games.id"))
    elo_before: Mapped[float] = mapped_column(Float)
    elo_after: Mapped[float] = mapped_column(Float)
    placement: Mapped[int] = mapped_column(SmallInteger)
    recorded_at: Mapped[datetime] = mapped_column(default=now)


class TrainingJob(Base):
    __tablename__ = "training_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20), default="TRAIN")  # TRAIN|SIMULATE
    config: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    checkpoint_url: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now)
    finished_at: Mapped[datetime | None] = mapped_column()


class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    final_ranking: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Challenge(Base):
    __tablename__ = "challenges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    challenger_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    opponent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    n_games: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    result: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now)


class ReplayAnnotation(Base):
    __tablename__ = "replay_annotations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    seq: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now)


class TutorProgress(Base):
    __tablename__ = "tutor_progress"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    quiz_score: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(default=now, onupdate=now)
