"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.db import get_session
from backend.models import User
from backend.security import TokenError, decode_token

SessionDep = Annotated[Session, Depends(get_session)]
_bearer = HTTPBearer(auto_error=False)


def _user_from(creds: HTTPAuthorizationCredentials | None, db: Session) -> User | None:
    if creds is None:
        return None
    try:
        claims = decode_token(creds.credentials, "access")
    except TokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from e
    user = db.get(User, claims["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    return user


def current_user(
    db: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    user = _user_from(creds, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    return user


def optional_user(
    db: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    return _user_from(creds, db)


UserDep = Annotated[User, Depends(current_user)]
OptionalUserDep = Annotated[User | None, Depends(optional_user)]
