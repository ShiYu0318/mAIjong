"""Sign-in tokens in WebSocket URLs must not reach the server logs."""

from __future__ import annotations

import logging

from backend.observability import TokenRedactor


def _render(msg: str, *args: object) -> str:
    rec = logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, msg, args, None)
    TokenRedactor().filter(rec)
    return rec.getMessage()


def test_tokens_are_masked_in_websocket_and_access_lines():
    line = _render('%s - "WebSocket %s" [accepted]', "172.18.0.1:4000",
                   "/ws/game/abc?token=eyJhbGciOi.eyJzdWIiOi.sig&batch=1")
    assert "eyJ" not in line and "token=***&batch=1" in line
    assert "token=***" in _render("GET /ws/game/x?token=secret HTTP/1.1")
    assert _render("plain %s", "no secrets here") == "plain no secrets here"
