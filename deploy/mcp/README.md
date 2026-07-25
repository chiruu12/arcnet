# SigNoz MCP server (Case File beat + dev-time authoring)

Plan pin: `v0.8.0` (docs/03). Upstream may lag — use the newest ≥ pin when available; otherwise pin the latest release and note drift in `docs/log.md`.

## Supported handoff path (G5)

**Product path = HTTP, not MCP stdio.** Operators and judges verify with:

```bash
.venv/bin/python scripts/verify_mcp_handoff.py
.venv/bin/python scripts/verify_mcp_handoff.py --session-id s_ecfdb55d
```

Walks: incident envelope → Case File zip → `/api/signoz/status` → `/api/signoz/evidence` → optional Query Range span probe (resolves `trace_id` from threat rows when the session row lacks one). Exits `0` on live span evidence, `2` when handoff works but SigNoz is down/keyless, `1` when the server/session path fails. Never prints secrets.

Stdio MCP is **optional enrichment only** — see [stdio diagnosis](#stdio-diagnosis) below.

## Env

Reuses root `.env`:

- `SIGNOZ_URL` (default `http://localhost:8080`)
- `SIGNOZ_API_KEY` (service-account key from SigNoz UI → Settings → Service Accounts)

Without `SIGNOZ_API_KEY`, the stdio binary exits immediately (`Configuration validation failed`). Cursor configs that pass the literal string `${SIGNOZ_API_KEY}` do **not** expand shell variables — use `wrap_stdio.sh` (loads `.env`) instead of the bare binary.

## Install (darwin arm64)

```bash
./deploy/mcp/install.sh
chmod +x deploy/mcp/wrap_stdio.sh deploy/mcp/diag_stdio.sh
```

Places binary at `deploy/mcp/bin/signoz-mcp-server` (gitignored).

## Cursor

Copy or merge `deploy/mcp/cursor-mcp.json` into your Cursor MCP config (`.cursor/mcp.json` at user or project level). Set `command` to the **absolute path** of `deploy/mcp/wrap_stdio.sh` in this repo — do not point at the bare binary and do not embed the API key in JSON.

## Claude Code

```bash
# after install.sh — wrap_stdio.sh sources .env for SIGNOZ_API_KEY
claude mcp add signoz --env SIGNOZ_URL=http://localhost:8080 \
  -- $(pwd)/deploy/mcp/wrap_stdio.sh
```

## Stdio diagnosis

```bash
./deploy/mcp/diag_stdio.sh
```

Findings (v0.8.0, measured 2026-07-25):

| Symptom | Cause | Fix |
|---------|-------|-----|
| IDE shows “connecting” forever | `SIGNOZ_API_KEY` missing — literal `${SIGNOZ_API_KEY}` in JSON, or `.env` not loaded | Use `wrap_stdio.sh`; confirm key in `.env` |
| Process exits code 1 instantly | Validation requires `SIGNOZ_API_KEY` for stdio mode | Add service-account key to `.env` |
| Manual run appears to hang | Server blocks on stdin waiting for MCP client (normal stdio behaviour) | Use an MCP host (Cursor/Claude); do not run bare binary in a terminal |
| Structured JSON on stderr | Upstream logs to stderr | Harmless for most MCP clients |

**Verdict:** stdio is not reliable enough for the demo handoff beat. Use `scripts/verify_mcp_handoff.py` + Case File HTTP links. For dev-time MCP tools, prefer `wrap_stdio.sh` or HTTP transport (below).

## Agent skills (dev-time)

```text
/plugin marketplace add SigNoz/agent-skills
/plugin install signoz@signoz-skills
```

Skills: generating-queries, writing-clickhouse-queries, creating-dashboards, creating-alerts, investigating-alerts.

## Docker alternative (HTTP transport)

```bash
docker run --rm -p 8001:8000 \
  -e TRANSPORT_MODE=http \
  -e MCP_SERVER_PORT=8000 \
  -e SIGNOZ_URL=http://host.docker.internal:8080 \
  -e SIGNOZ_API_KEY=$SIGNOZ_API_KEY \
  signoz/signoz-mcp-server:v0.6.0
```

(Use a non-8000 host port — ArcNet server owns 8000.)
