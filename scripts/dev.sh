#!/usr/bin/env bash
# Start the backend (port 8000) and frontend (port 3000) for local play.
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --inexact --extra backend --quiet   # keep the ai extra (torch) if installed
(cd frontend && pnpm install --silent)
trap 'kill 0' EXIT
# listen on every interface like `next dev`, so a phone on the same Wi-Fi can play too
# (DEV_HOST=127.0.0.1 keeps both on this machine only)
HOST="${DEV_HOST:-0.0.0.0}"
uv run --no-sync uvicorn backend.main:app --host "$HOST" --port 8000 &
(cd frontend && pnpm exec next dev -H "$HOST" -p 3000) &
LAN="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)"
echo "後端：http://localhost:8000   前端：http://localhost:3000"
if [ "$HOST" = "0.0.0.0" ] && [ -n "$LAN" ]; then
  echo "同一個 Wi-Fi 的手機或其他電腦：http://$LAN:3000"
fi
wait
