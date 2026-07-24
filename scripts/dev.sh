#!/usr/bin/env bash
# Start the SwarmOps API (:8000) and web (:3000) together for a live demo.
# Ctrl-C stops both. Run from the repository root (or via `make demo`).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="$ROOT/apps/api"
WEB="$ROOT/apps/web"

cleanup() {
  echo ""
  echo "Stopping SwarmOps…"
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "${WEB_PID:-}" ]] && kill "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting API on http://localhost:8000 …"
( cd "$API" && . .venv/bin/activate && exec uvicorn app.main:app --port 8000 ) &
API_PID=$!

# Wait for the API to answer /health before starting the web server.
for _ in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "API is up."
    break
  fi
  sleep 1
done

echo "Starting web on http://localhost:3000 …"
( cd "$WEB" && exec npm run dev ) &
WEB_PID=$!

echo ""
echo "SwarmOps is running:  API → http://localhost:8000   UI → http://localhost:3000"
echo "Open http://localhost:3000 and click 'Run demo mission'.  Press Ctrl-C to stop."
wait
