"""Lab dashboard API (SPEC 04.9, 09.1): simulations, comparisons, training, replays."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ai.training.metrics import read_metrics
from backend.deps import OptionalUserDep, SessionDep
from backend.models import Game, TrainingJob
from backend.tasks import runner

router = APIRouter(prefix="/lab", tags=["lab"])

BASE_AGENTS = ["random", "rule", "rule:1.5", "rule:3", "lv1", "lv2", "lv3", "lv4", "lv5"]


def available_agents() -> list[str]:
    out = list(BASE_AGENTS)
    ckpt = runner.ROOT / "checkpoints"
    if ckpt.exists():
        for p in sorted(ckpt.glob("*.pt")):
            kind = "ppo" if p.name.startswith(("ppo", "bc")) else "dqn"
            out.append(f"{kind}:{p}")
    return out


def _valid_spec(spec: str) -> bool:
    if spec in BASE_AGENTS or spec.startswith("rule:"):
        return True
    name, _, path = spec.partition(":")
    return name in ("ppo", "dqn") and Path(path).exists()


def job_out(j: TrainingJob) -> dict[str, Any]:
    return {"id": j.id, "kind": j.kind, "status": j.status, "config": j.config,
            "metrics": j.metrics, "checkpoint_url": j.checkpoint_url,
            "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}


@router.get("/agents")
def agents() -> list[str]:
    return available_agents()


class SimulateIn(BaseModel):
    seats: list[str] = Field(min_length=4, max_length=4)
    n_games: int = Field(200, ge=1, le=100_000)
    seed: int = 0


def _create_job(db: SessionDep, user: OptionalUserDep, kind: str, config: dict[str, Any]
                ) -> TrainingJob:
    job = TrainingJob(owner_id=user.id if user else None, kind=kind, config=config,
                      status="QUEUED", metrics={})
    db.add(job)
    db.commit()
    return job


@router.post("/simulate", status_code=status.HTTP_202_ACCEPTED)
def simulate(body: SimulateIn, db: SessionDep, user: OptionalUserDep) -> dict[str, str]:
    if not all(_valid_spec(s) for s in body.seats):
        raise HTTPException(422, "unknown agent")
    job = _create_job(db, user, "SIMULATE", body.model_dump())
    runner.submit_simulation(job.id, body.seats, body.n_games, body.seed)
    return {"job_id": job.id}


class CompareIn(BaseModel):
    agents: list[str] = Field(min_length=2, max_length=4)
    n_games: int = Field(400, ge=4, le=100_000)
    seed: int = 0


@router.post("/compare", status_code=status.HTTP_202_ACCEPTED)
def compare(body: CompareIn, db: SessionDep, user: OptionalUserDep) -> dict[str, str]:
    """Strategy comparison: agents fill the four seats in turn (seats rotate every hand)."""
    if not all(_valid_spec(s) for s in body.agents):
        raise HTTPException(422, "unknown agent")
    seats = [body.agents[i % len(body.agents)] for i in range(4)]
    job = _create_job(db, user, "COMPARE", {**body.model_dump(), "seats": seats})
    runner.submit_simulation(job.id, seats, body.n_games, body.seed)
    return {"job_id": job.id}


@router.get("/jobs")
def jobs(db: SessionDep, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.scalars(select(TrainingJob).order_by(TrainingJob.created_at.desc())
                      .limit(max(1, min(200, limit)))).all()
    return [job_out(j) for j in rows]


def _job(db: SessionDep, job_id: str) -> TrainingJob:
    j = db.get(TrainingJob, job_id)
    if j is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return j


@router.get("/jobs/{job_id}")
def job(job_id: str, db: SessionDep) -> dict[str, Any]:
    return job_out(_job(db, job_id))


class TrainIn(BaseModel):
    kind: Literal["ppo", "dqn", "bc"]
    config: dict[str, Any] = Field(default_factory=dict)


@router.post("/training", status_code=status.HTTP_202_ACCEPTED)
def start_training(body: TrainIn, db: SessionDep, user: OptionalUserDep) -> dict[str, str]:
    if body.kind == "bc" and not Path(str(body.config.get("data", ""))).exists():
        raise HTTPException(422, "BC needs config.data pointing to simulation records")
    job = _create_job(db, user, f"TRAIN_{body.kind.upper()}", body.config)
    job.checkpoint_url = str(runner.checkpoint_for(job.id, body.kind))
    db.commit()
    runner.start_training(job.id, body.kind, body.config)
    return {"job_id": job.id}


@router.get("/training/{job_id}")
def training(job_id: str, db: SessionDep) -> dict[str, Any]:
    j = _job(db, job_id)
    return {**job_out(j), "series": read_metrics(job_id)}


@router.post("/training/{job_id}/stop")
def stop(job_id: str, db: SessionDep) -> dict[str, Any]:
    _job(db, job_id)
    runner.stop_training(job_id)
    db.expire_all()
    return job_out(_job(db, job_id))


@router.post("/training/{job_id}/resume")
def resume(job_id: str, db: SessionDep) -> dict[str, Any]:
    j = _job(db, job_id)
    if not j.kind.startswith("TRAIN_"):
        raise HTTPException(422, "only training jobs can resume")
    kind = j.kind.removeprefix("TRAIN_").lower()
    config = dict(j.config)
    ckpt = runner.checkpoint_for(job_id, kind)
    if kind == "ppo" and ckpt.exists():
        config["init"] = str(ckpt)
    runner.start_training(job_id, kind, config)
    db.expire_all()
    return job_out(_job(db, job_id))


@router.get("/replays")
def replays(db: SessionDep, agent: str | None = None, result: str | None = None,
            min_tai: int = 0, tai_id: str | None = None, include_private: bool = False,
            limit: int = 50) -> list[dict[str, Any]]:
    """Replay explorer: filter finished hands by seat name/agent, outcome and tai."""
    rows = db.scalars(select(Game).order_by(Game.created_at.desc()).limit(5000)).all()
    out = []
    for g in rows:
        if not include_private and not g.is_public:
            continue
        r = g.result or {}
        if result == "DRAW" and r.get("kind") != "DRAW":
            continue
        if result in ("HU", "SELF_DRAW", "DEAL_IN") and r.get("kind") != "HU":
            continue
        if result == "SELF_DRAW" and not r.get("self_draw"):
            continue
        if result == "DEAL_IN" and r.get("self_draw"):
            continue
        items = r.get("tai_breakdown") or []
        if sum(i["tai"] for i in items) < min_tai:
            continue
        if tai_id and not any(i["id"] == tai_id for i in items):
            continue
        if agent and not any(s and agent in (s.get("name") or "") for s in g.seats):
            continue
        out.append({"id": g.id, "seats": g.seats, "result": r,
                    "created_at": g.created_at.isoformat()})
        if len(out) >= max(1, min(200, limit)):
            break
    return out
