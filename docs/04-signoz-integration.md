# ArcNet — SigNoz Integration (depth checklist)

"Best Use of SigNoz" is a scored judging category: *depth of platform integration across traces, metrics, logs, dashboards*. This doc is the contract for what we use and how. Check items off as they land.

## Deployment

- [ ] Self-hosted via Docker Compose (`deploy/`), pinned SigNoz version (record it here: ____)
- [ ] Service-account API key for Query Range API (server-side only, via env)
- Fallback: SigNoz Cloud trial if the Mac struggles — everything below works on both.

## Signals we emit

### Traces (OTLP)
Span hierarchy per OTel GenAI semantic conventions, plus our namespace:

- `invoke_agent` (root per run) → `chat` (LLM calls) → `execute_tool` (tool calls)
- GenAI attributes: `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`, input/output messages where the instrumentor supports content capture
- **`arcnet.guard` spans** (child of whatever triggered the check) with:
  - `arcnet.guard.checkpoint` = `input | retrieved | tool_call | output`
  - `arcnet.guard.action` = `allow | redact | block | review`
  - `arcnet.guard.risk_score` (0–1), `arcnet.guard.findings_count`
  - `arcnet.guard.top_category` (e.g. `injection`, `leakage`, `destructive`)
  - span events: one per `Finding` (`category`, `subcategory`, `score`, evidence excerpt)
  - `block` → span status ERROR (so SigNoz error rate/Apdex sees threats natively)
- Session identity on every span: `arcnet.session_id`, `arcnet.agent_id` (drives per-session alerts + Case File assembly)

### Metrics (OTLP)
- `gen_ai.client.token.usage` / `gen_ai.client.operation.duration` (from instrumentor)
- `arcnet.threats.detected` (counter; attrs: category, action, agent_id)
- `arcnet.guard.latency` (histogram — proves defense overhead is ms-level)
- `arcnet.cost.usd` (counter derived from tokens × model price — **price constants live in `sdk/arcnet/pricing.py`**, a small hardcoded `{model: (input_$/1k, output_$/1k)}` table for the 1–2 demo models; verified/written Day 0)
- `arcnet.tool.calls` (counter; attrs: tool, agent_id — feeds loop-depth alert)
- `arcnet.signals.emitted` (counter; attrs: kind)
- `arcnet.anomaly` (counter from Griffin; attrs: metric, agent_id, direction, severity — emitted **only** for true outliers)

### Logs (OTLP)
- Structured guard findings + agent lifecycle + signal deliveries, all carrying `trace_id`/`span_id` for correlation in SigNoz UI.

## SigNoz features we consume

- [ ] **Dashboards ×3, imported as JSON** (`deploy/provision/`):
  1. *Fleet Ops* — runs, latency, errors, active sessions
  2. *Threats & Security* — threat counts by category/agent, block rate, guard latency, recent findings (logs panel)
  3. *Cost & Tokens* — tokens + $ by agent/model, burn rate
  - ≥1 panel written in **ClickHouse SQL** (e.g. top attack subcategories from span events) — shows query-depth
- [ ] **Alert rules** (provisioned via API): threat>0 (1m), cost burn rate, tool-calls-per-session (loop), p99 latency, error rate, `arcnet.anomaly>0` (Griffin outliers)
- [ ] **Native anomaly-based alert** on ≥1 metric (SigNoz's built-in seasonal z-score alert type) — used alongside Griffin; README explains the pairing: SigNoz's seasonal model excels once history exists, Griffin (zero-shot TabFM) covers short-history agents from their first minutes
- [ ] **Webhook notification channel** → `POST /webhooks/signoz` (alert payload: grouped alerts, `fingerprint` for dedupe, `endsAt` for resolution — handle both firing + resolved)
- [ ] **Query Range API** (`POST /api/v*/query_range`, key auth) — powers HQ threat feed/session detail + Case File export. Basic call confirmed Day 0; validate full query shapes Day 2.
- [ ] **Metrics-listing endpoint** — Griffin's Discover step needs to enumerate available `arcnet.*`/`gen_ai.*` metrics. Confirm the endpoint (metrics metadata API or MCP `signoz_list_metrics`) Day 0; if none fits, fall back to a hardcoded metric allowlist (Griffin still works, just no auto-discovery).
- [ ] **Trace deep-links** from HQ into SigNoz trace view (judges see native UI too)
- [ ] **Agno dashboard template** imported (SigNoz ships one prebuilt — free depth points; our 3 custom dashboards sit alongside it)

## SigNoz AI surface (docs/ai/*) — use all of it that works self-hosted

- [ ] **SigNoz MCP server** (self-hosted binary/Docker; 40+ tools: `signoz_get_trace_details`, `signoz_search_logs`, `signoz_aggregate_traces`, `signoz_create_alert`, `signoz_import_dashboard`, `signoz_execute_builder_query`, …). Two roles:
  - **Dev-time**: wired into Cursor/Claude Code while building — author dashboards/alerts/queries with it, then freeze the JSON into `deploy/provision/`.
  - **Demo-time (Case File beat)**: case files embed `trace_id`s + instructions; the coding agent pulls live evidence via MCP and fixes the agent. Mirrors SigNoz's own "reconstruct a bug from a trace ID" / "postmortem evidence pack" use cases, specialized for agent security — name-check that in the README.
- [ ] **SigNoz agent skills** installed in the dev agent (`/plugin marketplace add SigNoz/agent-skills` → `/plugin install signoz@signoz-skills`): generating-queries, writing-clickhouse-queries, creating-dashboards, creating-alerts, investigating-alerts. Documented in README as part of our workflow (judges appreciate dogfooding their AI tooling).
- **Noz**: SigNoz Cloud-only (in-UI AI teammate) — out of scope for self-host. One line in README acknowledging it; if we ever flip to Cloud fallback, turn it on for the demo.

## Provisioning-as-code

`deploy/provision/setup.py`: idempotent — creates dashboards (import JSON), alert rules, webhook channel via SigNoz APIs. Judges reproduce with `docker compose up` + one script. Alert labels carry `agent_id`/`session_id` mapping so webhook → signal attribution works.

## Reference links

- Self-host install: https://signoz.io/docs/install/
- **Agno monitoring (our instrumentation, load-bearing): https://signoz.io/docs/agno-monitoring/**
- LLM observability overview: https://signoz.io/docs/llm-observability/
- Anomaly-based alerts (native seasonal): https://signoz.io/docs/alerts-management/anomaly-based-alerts/
- SigNoz MCP server: https://signoz.io/docs/ai/signoz-mcp-server/ · agent skills: https://signoz.io/docs/ai/agent-skills/
- Query Range API: https://signoz.io/docs/metrics-management/query-range-api/
- Traces ClickHouse schema: https://signoz.io/docs/userguide/writing-clickhouse-traces-query/
- Webhook channel: https://signoz.io/docs/alerts-management/notification-channel/webhook/
- OTel GenAI semconv: https://opentelemetry.io/blog/2026/genai-observability/
