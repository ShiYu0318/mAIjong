"""Password hashing and JWT tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from backend.config import get_settings

ALGORITHM = "HS256"
WS_TOKEN_TTL = timedelta(hours=12)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _encode(claims: dict[str, Any], ttl: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {**claims, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: str) -> str:
    ttl = timedelta(hours=get_settings().token_ttl_hours)
    return _encode({"sub": user_id, "kind": "access"}, ttl)


def create_ws_token(room_id: str, seat: int, user_id: str | None, name: str) -> str:
    return _encode(
        {"sub": user_id or "", "kind": "ws", "room": room_id, "seat": seat, "name": name},
        WS_TOKEN_TTL,
    )


class TokenError(ValueError):
    pass


def decode_token(token: str, kind: str) -> dict[str, Any]:
    try:
        claims: dict[str, Any] = jwt.decode(
            token, get_settings().secret_key, algorithms=[ALGORITHM]
        )
    except jwt.PyJWTError as e:
        raise TokenError(str(e)) from e
    if claims.get("kind") != kind:
        raise TokenError("wrong token kind")
    return claims
