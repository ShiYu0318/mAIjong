"""Optional error tracking (SPEC 12). With SENTRY_DSN set and `sentry-sdk` installed
(`uv pip install sentry-sdk`), unhandled errors are reported to Sentry."""

from __future__ import annotations

import logging
import os

log = logging.getLogger("maijong")


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
