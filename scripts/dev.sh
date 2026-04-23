#!/usr/bin/env bash
# scripts/dev.sh — bring the whole Kidroo stack up on localhost.
#
# Starts:
#   - FastAPI         on http://127.0.0.1:8000   (apps/api/main.py)
#   - Hatchet worker  (connects to Hatchet Cloud via HATCHET_CLIENT_TOKEN)
#   - Next.js dev     on http://127.0.0.1:3000   (apps/web)
#
# Requirements:
#   - `.env` at repo root (or real env vars) — see `.env.example`
#   - `apps/web/.env.local` with NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
#   - uv + pnpm installed (run `./SKILLS.sh` once to bootstrap)
#
# Usage:
#   ./scripts/dev.sh             # boot all three services, tail combined logs
#   ./scripts/dev.sh api worker  # boot a subset (omit names to exclude them)
#   ./scripts/dev.sh stop        # kill any running local services
#
# Logs land in `.logs/{api,worker,web}.log`. `.logs/` is gitignored.

set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
mkdir -p .logs

PIDDIR=".logs/pids"
mkdir -p "$PIDDIR"

_load_env() {
  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
}

_is_running() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

_start_api() {
  if _is_running "$PIDDIR/api.pid"; then
    echo "api already running (pid $(cat "$PIDDIR/api.pid"))"
    return
  fi
  echo "booting api on :8000 → .logs/api.log"
  nohup uv run uvicorn apps.api.main:app \
    --host 127.0.0.1 --port 8000 --reload \
    >> .logs/api.log 2>&1 &
  echo $! > "$PIDDIR/api.pid"
}

_start_worker() {
  if _is_running "$PIDDIR/worker.pid"; then
    echo "worker already running (pid $(cat "$PIDDIR/worker.pid"))"
    return
  fi
  if [[ -z "${HATCHET_CLIENT_TOKEN:-}" ]]; then
    echo "skip: HATCHET_CLIENT_TOKEN unset — worker cannot connect to Hatchet Cloud"
    return
  fi
  echo "booting worker → .logs/worker.log"
  nohup uv run python -m workflows.worker >> .logs/worker.log 2>&1 &
  echo $! > "$PIDDIR/worker.pid"
}

_start_web() {
  if _is_running "$PIDDIR/web.pid"; then
    echo "web already running (pid $(cat "$PIDDIR/web.pid"))"
    return
  fi
  echo "booting web on :3000 → .logs/web.log"
  nohup pnpm --filter web dev >> .logs/web.log 2>&1 &
  echo $! > "$PIDDIR/web.pid"
}

_stop_all() {
  local stopped=0
  for name in api worker web; do
    local pidfile="$PIDDIR/$name.pid"
    if _is_running "$pidfile"; then
      local pid
      pid="$(cat "$pidfile")"
      echo "stopping $name (pid $pid)"
      kill "$pid" 2>/dev/null || true
      rm -f "$pidfile"
      stopped=1
    fi
  done
  # Nuke any orphaned next/uvicorn/worker processes too.
  pkill -f 'workflows.worker' 2>/dev/null || true
  pkill -f 'uvicorn apps.api.main' 2>/dev/null || true
  pkill -f 'next dev --turbopack' 2>/dev/null || true
  if [[ $stopped -eq 0 ]]; then
    echo "nothing was running"
  fi
}

case "${1:-all}" in
  stop)
    _stop_all
    exit 0
    ;;
  all|"")
    services=(api worker web)
    ;;
  *)
    services=("$@")
    ;;
esac

_load_env

for svc in "${services[@]}"; do
  case "$svc" in
    api)    _start_api    ;;
    worker) _start_worker ;;
    web)    _start_web    ;;
    *)      echo "unknown service: $svc (expected: api|worker|web|stop)"; exit 2 ;;
  esac
done

cat <<EOF

ready.
  api:    http://127.0.0.1:8000/health
  web:    http://127.0.0.1:3000/login
  logs:   tail -f .logs/{api,worker,web}.log
  stop:   ./scripts/dev.sh stop
EOF
