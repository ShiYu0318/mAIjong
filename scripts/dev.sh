#!/usr/bin/env bash
# Start the backend (port 8000) and frontend (port 3000) for local play.
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --extra backend --quiet
(cd frontend && pnpm install --silent)
trap 'kill 0' EXIT
uv run uvicorn backend.main:app --port 8000 &
(cd frontend && pnpm exec next dev -p 3000) &
echo "後端：http://localhost:8000   前端：http://localhost:3000"
wait
