"""Guest accounts and player progression API (docs design §8)."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select

from backend import progression
from backend.deps import SessionDep, UserDep
from backend.models import User
from backend.routers.auth import AuthOut, user_out
from backend.security import create_access_token, hash_password

router = APIRouter(tags=["profile"])


@router.post("/auth/guest", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def guest(db: SessionDep) -> AuthOut:
    """Instant account with a random nickname; upgrade later to keep it across devices."""
    for _ in range(20):
        name = f"訪客{secrets.randbelow(900000) + 100000}"
        if db.scalar(select(User).where(User.username == name)) is None:
            break
    else:  # pragma: no cover - 900k names
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "try again")
    user = User(username=name, email=f"guest-{uuid.uuid4().hex}@guest.invalid",
                password_hash=None, is_guest=True)
    db.add(user)
    db.flush()
    progression.get_progress(db, user)
    db.commit()
    return AuthOut(token=create_access_token(user.id), user=user_out(user))


class UpgradeIn(BaseModel):
    username: str = Field(min_length=2, max_length=30, pattern=r"^[\w\-一-鿿]+$")
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


@router.post("/auth/upgrade", response_model=AuthOut)
def upgrade(body: UpgradeIn, db: SessionDep, user: UserDep) -> AuthOut:
    """Turn a guest into a full account, keeping all progress."""
    if not user.is_guest:
        raise HTTPException(status.HTTP_409_CONFLICT, "already a registered account")
    taken = db.scalar(select(User).where(
        or_(User.username == body.username, User.email == body.email), User.id != user.id))
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "username or email already taken")
    user.username = body.username
    user.email = body.email
    user.password_hash = hash_password(body.password)
    user.is_guest = False
    db.commit()
    return AuthOut(token=create_access_token(user.id), user=user_out(user))


@router.get("/profile/me")
def my_profile(db: SessionDep, user: UserDep) -> dict[str, Any]:
    data = progression.profile(db, user)
    db.commit()  # first visit of the day assigns missions
    return {"user": user_out(user).model_dump(), **data}


@router.post("/profile/bonus")
def claim_bonus(db: SessionDep, user: UserDep) -> dict[str, Any]:
    p = progression.get_progress(db, user)
    try:
        amount = progression.claim_bonus(p)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.commit()
    return {"amount": amount, "coins": p.coins, "streak": p.bonus_streak}


@router.post("/profile/missions/{mission_id}/claim")
def claim_mission(mission_id: str, db: SessionDep, user: UserDep) -> dict[str, Any]:
    p = progression.get_progress(db, user)
    try:
        reward = progression.claim_mission(p, mission_id)
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such mission today") from e
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.commit()
    return {"reward": reward, "coins": p.coins}


@router.get("/shop")
def shop(db: SessionDep, user: UserDep) -> dict[str, Any]:
    p = progression.get_progress(db, user)
    db.commit()
    return {"coins": p.coins, "items": progression.shop(p)}


class ItemIn(BaseModel):
    slot: str
    item: str


@router.post("/shop/buy")
def buy(body: ItemIn, db: SessionDep, user: UserDep) -> dict[str, Any]:
    p = progression.get_progress(db, user)
    try:
        progression.buy(p, body.slot, body.item)
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such item") from e
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.commit()
    return {"coins": p.coins, "items": progression.shop(p)}


@router.post("/profile/equip")
def equip(body: ItemIn, db: SessionDep, user: UserDep) -> dict[str, Any]:
    p = progression.get_progress(db, user)
    try:
        progression.equip(p, body.slot, body.item)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.commit()
    return {"equipped": p.equipped}
