#!/usr/bin/env bash
# Diagnose SigNoz MCP stdio transport — run from repo root after install.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="$ROOT/deploy/mcp/bin/signoz-mcp-server"
WRAP="$ROOT/deploy/mcp/wrap_stdio.sh"

echo "=== SigNoz MCP stdio diagnosis (v0.8.0 pin) ==="

if [[ ! -x "$BIN" ]]; then
  echo "FAIL: binary missing — run ./deploy/mcp/install.sh"
  exit 1
fi

echo
echo "1) Missing SIGNOZ_API_KEY (common when Cursor config uses literal \${SIGNOZ_API_KEY})"
if SIGNOZ_API_KEY= SIGNOZ_URL=http://localhost:8080 timeout 3 "$BIN" >/dev/null 2>"/tmp/signoz-mcp-diag-$$.err"; then
  echo "   unexpected: server started without key"
else
  code=$?
  msg="$(head -1 "/tmp/signoz-mcp-diag-$$.err" 2>/dev/null || true)"
  echo "   exit $code — $msg"
  echo "   fix: point Cursor/Claude at deploy/mcp/wrap_stdio.sh (loads .env) instead of the bare binary"
fi
rm -f "/tmp/signoz-mcp-diag-$$.err"

echo
echo "2) Valid key, no MCP client (blocking stdin read — looks like a hang if launched manually)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
if [[ -z "${SIGNOZ_API_KEY:-}" ]]; then
  echo "   SKIP: .env has no SIGNOZ_API_KEY"
else
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$BIN" <<'PY'
import os, subprocess, sys, time
bin_path = sys.argv[1]
env = {"SIGNOZ_URL": os.environ.get("SIGNOZ_URL", "http://localhost:8080"), "SIGNOZ_API_KEY": os.environ["SIGNOZ_API_KEY"]}
p = subprocess.Popen([bin_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
time.sleep(2)
if p.poll() is None:
    print("   server still running after 2s with no stdin — expected stdio blocking read")
    p.terminate()
else:
    print(f"   exited early code={p.returncode} (check OTLP/metrics logs on stderr)")
PY
  else
    echo "   SKIP: python3 not available"
  fi
fi

echo
echo "3) wrap_stdio.sh loads .env before exec"
if [[ -x "$WRAP" ]]; then
  if [[ -n "${SIGNOZ_API_KEY:-}" ]]; then
    echo "   SIGNOZ_API_KEY present in .env — wrapper ready"
  else
    echo "   wrapper exists; add SIGNOZ_API_KEY to .env for live MCP tools"
  fi
else
  echo "   FAIL: $WRAP not executable"
fi

echo
echo "=== Verdict ==="
echo "Supported product path: HTTP handoff — .venv/bin/python scripts/verify_mcp_handoff.py"
echo "Optional dev path: MCP stdio via wrap_stdio.sh + IDE client; HTTP transport via TRANSPORT_MODE=http (see deploy/mcp/README.md)"
