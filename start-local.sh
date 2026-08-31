#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PID=""
WORKER_PID=""
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ergoagent.XXXXXX")"
FRONTEND_URL="http://127.0.0.1:5173"

cleanup() {
  if [[ -n "$WORKER_PID" ]] && kill -0 "$WORKER_PID" 2>/dev/null; then
    kill "$WORKER_PID" 2>/dev/null || true
  fi
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
  fi
  rm -rf "$LOG_DIR"
}

trap cleanup EXIT INT TERM

require_file() {
  if [[ ! -e "$1" ]]; then
    echo "Missing $1. Follow the environment setup steps in README.md first." >&2
    exit 1
  fi
}

require_file "$ROOT_DIR/.venv/bin/uvicorn"
require_file "$ROOT_DIR/.venv/bin/alembic"
require_file "$ROOT_DIR/.venv-vision312/bin/python"

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$ROOT_DIR/frontend" && npm install)
fi

echo "Preparing database..."
(cd "$ROOT_DIR" && .venv/bin/alembic upgrade head)

if curl --fail --silent --show-error http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "Analysis API already available at http://127.0.0.1:8000"
else
  echo "Starting analysis API..."
  (cd "$ROOT_DIR" && .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload >"$LOG_DIR/api.log" 2>&1) &
  API_PID=$!
  for _ in {1..20}; do
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  if ! curl --fail --silent http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "Analysis API did not start. Log: $LOG_DIR/api.log" >&2
    exit 1
  fi
fi

echo "Starting vision worker..."
if pgrep -f "[.]venv-vision312/bin/python -m app.worker" >/dev/null; then
  echo "Vision worker already running"
else
  (cd "$ROOT_DIR" && .venv-vision312/bin/python -m app.worker >"$LOG_DIR/worker.log" 2>&1) &
  WORKER_PID=$!
fi

if curl --fail --silent "$FRONTEND_URL" >/dev/null 2>&1; then
  echo "Frontend already available at $FRONTEND_URL"
  echo "Open $FRONTEND_URL. Press Ctrl+C to stop services started by this script."
  while true; do sleep 60; done
fi

echo "ErgoAgent is ready at $FRONTEND_URL"
echo "Press Ctrl+C to stop the API, worker, and frontend server."
cd "$ROOT_DIR/frontend"
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
