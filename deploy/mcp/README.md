# SigNoz MCP server (Case File beat + dev-time authoring)

Plan pin: `v0.8.0` (docs/03). Upstream may lag — use the newest ≥ pin when available; otherwise pin the latest release and note drift in `docs/log.md`.

## Env

Reuses root `.env`:

- `SIGNOZ_URL` (default `http://localhost:8080`)
- `SIGNOZ_API_KEY` (service-account key from SigNoz UI → Settings → Service Accounts)

Without `SIGNOZ_API_KEY`, MCP tools that hit Query Range / APIs will fail — binary still installs.

## Install (darwin arm64)

```bash
./deploy/mcp/install.sh
```

Places binary at `deploy/mcp/bin/signoz-mcp-server`.

## Cursor

Copy or merge `deploy/mcp/cursor-mcp.json` into your Cursor MCP config (`.cursor/mcp.json` at user or project level). Paths are absolute — edit `command` if you move the repo.

## Claude Code

```bash
# after install.sh
claude mcp add signoz --env SIGNOZ_URL=$SIGNOZ_URL --env SIGNOZ_API_KEY=$SIGNOZ_API_KEY \
  -- $(pwd)/deploy/mcp/bin/signoz-mcp-server
```

## Agent skills (dev-time)

```text
/plugin marketplace add SigNoz/agent-skills
/plugin install signoz@signoz-skills
```

Skills: generating-queries, writing-clickhouse-queries, creating-dashboards, creating-alerts, investigating-alerts.

## Docker alternative

```bash
docker run --rm -p 8001:8000 \
  -e TRANSPORT_MODE=http \
  -e MCP_SERVER_PORT=8000 \
  -e SIGNOZ_URL=http://host.docker.internal:8080 \
  -e SIGNOZ_API_KEY=$SIGNOZ_API_KEY \
  signoz/signoz-mcp-server:v0.6.0
```

(Use a non-8000 host port — ArcNet server owns 8000.)
