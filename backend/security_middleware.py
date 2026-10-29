"""Rate limiting and security headers (SPEC P11-8)."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class TokenBucket:
    """Per-key token bucket: `rate` tokens per `per` seconds, burst up to `rate`."""

    def __init__(self, rate: float, per: float) -> None:
        self.rate = rate
        self.per = per
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._state.get(key, (self.rate, now))
            tokens = min(self.rate, tokens + (now - last) * self.rate / self.per)
            if tokens < 1:
                self._state[key] = (tokens, now)
                return False
            self._state[key] = (tokens - 1, now)
            if len(self._state) > 50_000:  # forget idle clients
                self._state = {k: v for k, v in self._state.items() if now - v[1] < self.per}
            return True


def client_ip(request: Request) -> str:
    """The player's address. Behind a proxy (Cloudflare, Fly.io, nginx) every request comes
    from the proxy, so set TRUSTED_PROXY_HEADER to the header it fills in (CF-Connecting-IP,
    Fly-Client-IP or X-Forwarded-For). Only do that when the backend can be reached solely
    through the proxy: otherwise anyone can send the header and pick their own address."""
    header = os.environ.get("TRUSTED_PROXY_HEADER", "").strip()
    if header:
        value = request.headers.get(header, "")
        if header.lower() == "x-forwarded-for":
            value = value.split(",")[-1]  # the proxy appends; the left part is the client's
        if value.strip():
            return value.strip()
    return request.client.host if request.client else "unknown"


def _limit(name: str, default: str) -> float:
    return float(os.environ.get(name, default))


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.auth = TokenBucket(_limit("RATE_LIMIT_AUTH_PER_MIN", "10"), 60)
        self.api = TokenBucket(_limit("RATE_LIMIT_API_PER_MIN", "300"), 60)

    async def dispatch(self, request: Request,
                       call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        ip = client_ip(request)
        path = request.url.path
        if path.startswith("/api/"):
            bucket = self.auth if path.startswith("/api/v1/auth/") and request.method == "POST" \
                else self.api
            if not bucket.allow(ip):
                return JSONResponse({"detail": "too many requests, slow down"}, status_code=429,
                                    headers={"Retry-After": "10"})
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy",
                                    "camera=(), microphone=(), geolocation=()")
        return response


def clean_text(text: str, limit: int = 200) -> str:
    """Strip control characters and trim (chat, notes)."""
    out = "".join(ch for ch in text if ch == "\n" or ch >= " " and ch != "\x7f")
    return out.strip()[:limit]
