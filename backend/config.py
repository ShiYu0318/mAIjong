"""Runtime settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(os.environ.get("MAIJONG_DATA_DIR", "data"))


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = f"sqlite:///{DATA_DIR / 'maijong.db'}"
    secret_key: str = "dev-only-secret-key-change-me-in-production"
    redis_url: str | None = None
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])
    debug: bool = False
    token_ttl_hours: int = 24 * 7
    replay_dir: Path = DATA_DIR / "replays"
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    hint_llm_provider: str | None = None
    hint_llm_api_key: str | None = None
    grace_period_sec: float = 30.0
    reconnect_window_sec: float = 300.0
    default_bot_level: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = os.environ
    defaults = Settings()
    return Settings(
        database_url=env.get("DATABASE_URL", defaults.database_url),
        secret_key=env.get("SECRET_KEY", defaults.secret_key),
        redis_url=env.get("REDIS_URL") or None,
        cors_origins=_csv(env["CORS_ORIGINS"]) if "CORS_ORIGINS" in env else defaults.cors_origins,
        debug=env.get("DEBUG", "").lower() in ("1", "true", "yes"),
        token_ttl_hours=int(env.get("TOKEN_TTL_HOURS", defaults.token_ttl_hours)),
        replay_dir=Path(env.get("REPLAY_DIR", str(defaults.replay_dir))),
        s3_endpoint=env.get("S3_ENDPOINT") or None,
        s3_bucket=env.get("S3_BUCKET") or None,
        s3_access_key=env.get("S3_ACCESS_KEY") or None,
        s3_secret_key=env.get("S3_SECRET_KEY") or None,
        hint_llm_provider=env.get("HINT_LLM_PROVIDER") or None,
        hint_llm_api_key=env.get("HINT_LLM_API_KEY") or None,
        grace_period_sec=float(env.get("GRACE_PERIOD_SEC", defaults.grace_period_sec)),
        reconnect_window_sec=float(
            env.get("RECONNECT_WINDOW_SEC", defaults.reconnect_window_sec)
        ),
        default_bot_level=int(env.get("DEFAULT_BOT_LEVEL", defaults.default_bot_level)),
    )
