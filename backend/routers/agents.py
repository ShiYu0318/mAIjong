"""Community agent submissions (SPEC 06.4, 09.1, P9-6).

A submission zip holds agent.py, manifest.json, requirements.txt and optionally
model.pt. It is stored under data/agents/<id>/, validated in the sandbox (10 hands
against random opponents) and, if it passes, joins the arena at rating 1500.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import func, select

from backend.config import DATA_DIR
from backend.db import session_factory
from backend.deps import SessionDep, UserDep
from backend.models import Agent, EloHistory, User

router = APIRouter(prefix="/agents", tags=["agents"])
log = logging.getLogger("maijong.agents")

MAX_ZIP_BYTES = 200 * 1024 * 1024
ALLOWED_FILES = {"agent.py", "manifest.json", "requirements.txt", "model.pt"}
ALLOWED_REQUIREMENTS = {"torch", "numpy"}


def agents_dir() -> Path:
    return DATA_DIR / "agents"


def agent_out(a: Agent, owner: str | None = None) -> dict[str, Any]:
    return {
        "id": a.id, "name": a.name, "version": a.version, "elo": round(a.elo, 1),
        "games_played": a.games_played, "status": a.status, "owner": owner,
        "owner_id": a.owner_id, "description": a.manifest.get("description", ""),
        "validation": a.manifest.get("validation"), "model_sha256": a.model_sha256,
        "created_at": a.created_at.isoformat(),
    }


def _check_zip(raw: bytes) -> tuple[dict[str, Any], zipfile.ZipFile]:
    if len(raw) > MAX_ZIP_BYTES:
        raise HTTPException(413, "submission larger than 200 MB")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as e:
        raise HTTPException(422, "not a zip file") from e
    names = set(z.namelist())
    if not {"agent.py", "manifest.json"} <= names:
        raise HTTPException(422, "submission needs agent.py and manifest.json")
    if names - ALLOWED_FILES:
        raise HTTPException(422, f"unexpected files: {sorted(names - ALLOWED_FILES)}")
    try:
        manifest = json.loads(z.read("manifest.json"))
    except ValueError as e:
        raise HTTPException(422, "manifest.json is not valid JSON") from e
    if not isinstance(manifest.get("agent_class"), str) or not manifest.get("name"):
        raise HTTPException(422, "manifest needs agent_class and name")
    if "requirements.txt" in names:
        for line in z.read("requirements.txt").decode().splitlines():
            pkg = line.split("=")[0].split("<")[0].split(">")[0].strip().lower()
            if pkg and not pkg.startswith("#") and pkg not in ALLOWED_REQUIREMENTS:
                raise HTTPException(422, f"requirement {pkg!r} is not allowed")
    return manifest, z


def _validate_later(agent_id: str, directory: Path) -> None:
    def run() -> None:
        from maijong_sdk.validation import validate_submission

        try:
            report = validate_submission(directory, games=10)
        except Exception as e:  # never leave a submission stuck in PENDING
            report = {"passed": False, "errors": [f"{type(e).__name__}: {e}"]}
        with session_factory()() as db:
            a = db.get(Agent, agent_id)
            if a is None:
                return
            a.status = "ACTIVE" if report["passed"] else "REJECTED"
            a.manifest = {**a.manifest, "validation": report}
            db.commit()

    threading.Thread(target=run, daemon=True).start()


@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit(file: Annotated[UploadFile, File()], db: SessionDep, user: UserDep
                 ) -> dict[str, Any]:
    raw = await file.read()
    manifest, z = _check_zip(raw)
    name = str(manifest["name"])[:100]
    version = (db.scalar(select(func.max(Agent.version)).where(
        Agent.owner_id == user.id, Agent.name == name)) or 0) + 1
    agent = Agent(owner_id=user.id, name=name, version=version, manifest=manifest,
                  status="PENDING")
    db.add(agent)
    db.flush()
    directory = agents_dir() / agent.id
    directory.mkdir(parents=True, exist_ok=True)
    z.extractall(directory)
    (directory / "submission.zip").write_bytes(raw)
    model = directory / "model.pt"
    agent.model_sha256 = hashlib.sha256(model.read_bytes()).hexdigest() if model.exists() else None
    agent.submission_path = str(directory)
    db.commit()
    _validate_later(agent.id, directory)
    return agent_out(agent, user.username)


@router.get("")
def list_agents(db: SessionDep, page: int = 1, sort: str = "elo", status_: str = "ACTIVE",
                limit: int = 50) -> list[dict[str, Any]]:
    order = Agent.elo.desc() if sort == "elo" else Agent.created_at.desc()
    q = select(Agent, User.username).join(User, User.id == Agent.owner_id, isouter=True)
    if status_ != "ALL":
        q = q.where(Agent.status == status_)
    limit = max(1, min(100, limit))
    rows = db.execute(q.order_by(order).offset((max(1, page) - 1) * limit).limit(limit)).all()
    return [agent_out(a, owner) for a, owner in rows]


@router.get("/{agent_id}")
def get_agent(agent_id: str, db: SessionDep) -> dict[str, Any]:
    a = db.get(Agent, agent_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent not found")
    owner = db.get(User, a.owner_id) if a.owner_id else None
    history = db.scalars(select(EloHistory).where(EloHistory.agent_id == agent_id)
                         .order_by(EloHistory.recorded_at)).all()
    return {**agent_out(a, owner.username if owner else None),
            "elo_history": [{"elo": h.elo_after, "placement": h.placement,
                             "at": h.recorded_at.isoformat()} for h in history]}


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, db: SessionDep, user: UserDep) -> None:
    a = db.get(Agent, agent_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent not found")
    if a.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your agent")
    a.status = "DELETED"
    db.commit()
    if a.submission_path:
        shutil.rmtree(a.submission_path, ignore_errors=True)
