#!/usr/bin/env bash
# Launch SigNoz MCP stdio with repo .env loaded (SIGNOZ_API_KEY never echoed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
: "${SIGNOZ_URL:=http://localhost:8080}"
if [[ -z "${SIGNOZ_API_KEY:-}" ]]; then
  echo "signoz-mcp: SIGNOZ_API_KEY missing — add a service-account key to .env (SigNoz UI → Settings → Service Accounts)" >&2
  exit 1
fi
exec "$ROOT/deploy/mcp/bin/signoz-mcp-server" "$@"
