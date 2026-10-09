from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select

from backend.deps import SessionDep, UserDep
from backend.models import User
from backend.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=30, pattern=r"^[\w\-一-鿿]+$")
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    elo_human: float
    games_played: int


class AuthOut(BaseModel):
    token: str
    user: UserOut


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, username=u.username, email=u.email,
        elo_human=u.elo_human, games_played=u.games_played,
    )


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: SessionDep) -> AuthOut:
    exists = db.scalar(
        select(User).where(or_(User.username == body.username, User.email == body.email))
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "username or email already taken")
    user = User(username=body.username, email=body.email,
                password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return AuthOut(token=create_access_token(user.id), user=user_out(user))


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, db: SessionDep) -> AuthOut:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong email or password")
    return AuthOut(token=create_access_token(user.id), user=user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: UserDep) -> UserOut:
    return user_out(user)
