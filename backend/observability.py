"""Optional error tracking (SPEC 12). With SENTRY_DSN set and `sentry-sdk` installed
(`uv pip install sentry-sdk`), unhandled errors are reported to Sentry."""

from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("maijong")

_TOKEN = re.compile(r"(token=)[^&\s\"]+")


class TokenRedactor(logging.Filter):
    """WebSocket URLs carry a sign-in token (?token=...); uvicorn logs the URL of every
    connection and request, so the token would land in the logs for anyone who reads them."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_TOKEN.sub(r"\1***", a) if isinstance(a, str) else a
                                for a in record.args)
        if isinstance(record.msg, str):
            record.msg = _TOKEN.sub(r"\1***", record.msg)
        return True


def redact_tokens_in_server_logs() -> None:
    for name in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).addFilter(TokenRedactor())


def init_sentry() -> bool:
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        log.warning("SENTRY_DSN is set but sentry-sdk is not installed; errors are not reported")
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=False,
    )
    return True
