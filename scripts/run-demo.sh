#!/usr/bin/env bash
# ArcNet one-command demo bring-up (Phase 5, docs/03).
#
# Starts the control plane + agent runtime + HQ UI against data/arcnet.db,
# seeding Griffin history and the background fleet first. SigNoz/Docker is
# optional: everything here is SQLite-primary and runs without containers.
#
#   ./scripts/run-demo.sh            # seed + start everything
#   ./scripts/run-demo.sh --no-seed  # just start services
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SERVER_PORT="${ARCNET_SERVER_PORT:-8000}"
AGENTOS_PORT="${ARCNET_AGENTOS_PORT:-7777}"
HQ_PORT="${HQ_PORT:-5173}"
PIDS=()

cleanup() {
  echo
  echo "demo.stop() — shutting down"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "error: .venv missing — run 'uv sync' first" >&2
  exit 1
fi

if [[ "${1:-}" != "--no-seed" ]]; then
  echo "seed.griffin() — MAD history"
  .venv/bin/python scripts/seed.py
  echo "seed.fleet() — background agents"
  .venv/bin/python scripts/seed_demo.py
fi

port_free() {
  if command -v lsof >/dev/null 2>&1; then
    ! lsof -ti ":$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    ! (echo >/dev/tcp/127.0.0.1/"$1") >/dev/null 2>&1
  fi
}

if port_free "$SERVER_PORT"; then
  echo "arcnet-server.start() — :$SERVER_PORT"
  .venv/bin/uvicorn arcnet_server.main:app --host 127.0.0.1 --port "$SERVER_PORT" --app-dir server &
  PIDS+=($!)
else
  echo "arcnet-server already listening on :$SERVER_PORT — reusing"
fi

if port_free "$AGENTOS_PORT"; then
  echo "agentos.start() — :$AGENTOS_PORT (replay runtime)"
  .venv/bin/uvicorn arcnet_agents.app:app --host 127.0.0.1 --port "$AGENTOS_PORT" --app-dir agents &
  PIDS+=($!)
else
  echo "agentos already listening on :$AGENTOS_PORT — reusing"
fi

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$SERVER_PORT/health" >/dev/null; then break; fi
  sleep 0.5
done
curl -sf "http://127.0.0.1:$SERVER_PORT/health" >/dev/null || {
  echo "error: arcnet-server failed to come up" >&2
  exit 1
}
echo "arcnet-server healthy"

echo "hq.start() — :$HQ_PORT"
echo
echo "  fleet_health  http://localhost:$HQ_PORT"
echo "  api           http://127.0.0.1:$SERVER_PORT/api/fleet"
echo "  case file     http://127.0.0.1:$SERVER_PORT/export/case-file/<session_id>"
echo
echo "note: SigNoz dashboards are optional (Docker); replay + case files are SQLite-primary."
echo "Ctrl-C stops everything."
echo
(cd hq && pnpm dev --port "$HQ_PORT")
