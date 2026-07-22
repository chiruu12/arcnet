# ArcNet — SigNoz Integration (depth checklist)

"Best Use of SigNoz" is a scored judging category: *depth of platform integration across traces, metrics, logs, dashboards*. This doc is the contract for what we use and how. Check items off as they land.

## Deployment

- [x] Self-hosted via Foundry → Docker Compose (`deploy/casting.yaml` + `deploy/docker-compose.yaml` → `pours/deployment/compose.yaml`), **pinned SigNoz `v0.133.0`** (Foundry `foundryctl` v0.2.15). Bring-up: `cd deploy && foundryctl cast -f casting.yaml`.
- [x] Service-account API key for Query Range API (server-side only, via env) — **cannot be created headlessly** (no public create-key API without an existing admin session; docs confirm Settings → Service Accounts UI). **Manual one-time step documented in README.** Phase 6 evidence: key present in `.env` (gitignored); `/api/v1/service_accounts/me` → 200 for account `tmp`. **Role required:** assign `signoz-admin` (or editor/viewer) via UI or `POST /api/v1/service_accounts/{id}/roles` with admin JWT — key alone with `serviceAccountRoles: null` authenticates but returns `authz_forbidden` on Query Range / dashboards / rules.
- Fallback: SigNoz Cloud trial if the Mac struggles — everything below works on both.
- **Mac resources (Phase 0):** Docker Desktop 10 CPUs / 7.65 GiB. Steady-state RSS ≈ ClickHouse 1.2 GiB + keeper 120 MiB + postgres 73 MiB + signoz 45 MiB + ingester 46 MiB (~1.5 GiB total). Comfortable on this machine; keep ≥4 GiB Docker memory.
- **Phase 6 re-bring-up (2026-07-22):** same pinned `signoz/signoz:v0.133.0` via `foundryctl` v0.2.15; healthy in <1 min, `/api/v1/health` ok, version endpoint confirms `v0.133.0`. RSS slightly above the Phase 0 note: ClickHouse ~1.55 GiB, keeper ~265 MiB, signoz ~118 MiB (still well within budget). **Drift:** Foundry-generated compose runs the ingester as `signoz/signoz-otel-collector:latest` (unpinned by the generator; only the signoz image is pinned via `casting.yaml`).

## Signals we emit

### Traces (OTLP)
Span hierarchy **as the pinned instrumentor actually emits it** — OpenInference semconv, NOT `gen_ai.*`. **Phase 0 live trace (2026-07-21) recorded below — author all dashboards/alerts against these keys only:**

**Live span names (hello agent `name="hello_arcnet"`, model `OpenAIChat(gpt-4o-mini)`, tool `add`):**
- `hello_arcnet.run` — root, `openinference.span.kind=AGENT`
- `OpenAIChat.invoke` — LLM calls, `openinference.span.kind=LLM` (pattern = `{ModelClass}.invoke`, not the model id)
- `add` — tool call, `openinference.span.kind=TOOL` (pattern = tool function name)

**Live attribute keys on LLM spans (ClickHouse `attributes_string` / `attributes_number`):**
- `openinference.span.kind` ∈ `AGENT` | `LLM` | `TOOL`
- `llm.model_name` (e.g. `gpt-4o-mini`), `llm.provider` (e.g. `OpenAI`)
- `llm.token_count.prompt`, `llm.token_count.completion` — stored as **numbers** in ClickHouse (`attributes_number`)
- `llm.input_messages.{i}.message.role` / `.content` / `.tool_call_id` / nested `.tool_calls…`
- `llm.output_messages.{i}.message.role` / `.content` / `.tool_calls…`
- `llm.tools.{i}.tool.json_schema`
- `input.value`, `input.mime_type`, `output.value`, `output.mime_type`
- TOOL spans also: `tool.name`, `tool.description`, `tool.parameters`
- AGENT spans also: `agno.tools` (tuple of tool names)
- **Zero `gen_ai.*` keys observed** — do not author against them

**Oversized-fixture (Phase 0):** SDK + this self-hosted collector/ClickHouse accepted attribute payloads through **256 KB** with no truncation observed (`stored_len` matched requested). Still keep transcripts **SQLite-primary** — backend ceilings vary by config/version; full tool outputs must not depend on span attrs.
- **`arcnet.guard` spans** (child of whatever triggered the check) with:
  - `arcnet.guard.checkpoint` = `input | retrieved | tool_call | output`
  - `arcnet.guard.action` = `allow | redact | block | review`
  - `arcnet.guard.risk_score` (0–1), `arcnet.guard.findings_count`
  - `arcnet.guard.top_category` (e.g. `injection`, `leakage`, `destructive`)
  - span events: one per `Finding` (`category`, `subcategory`, `score`, evidence excerpt)
  - `block` → span status ERROR (so SigNoz error rate/Apdex sees threats natively)
- Session identity on every span: `arcnet.session_id`, `arcnet.agent_id` (drives per-session alerts + Case File assembly)

### Metrics (OTLP)
- `arcnet.tokens.total` / `arcnet.llm.duration` — derived by **our SDK** from Agno's per-run metrics and emitted as real OTLP counters/histograms (the instrumentor itself emits token counts only as span attributes, not metrics — never assume `gen_ai.*` metrics exist)
- `arcnet.threats.detected` (counter; attrs: category, action, agent_id)
- `arcnet.guard.latency` (histogram — proves defense overhead is ms-level)
- `arcnet.cost.usd` (counter derived from tokens × model price — **price constants live in `sdk/arcnet/pricing.py`**, a small hardcoded `{model: (input_$/1k, output_$/1k)}` table for the 1–2 demo models; verified/written in Phase 0)
- `arcnet.tool.calls` (counter; attrs: tool, agent_id — feeds loop-depth alert)
- `arcnet.signals.emitted` (counter; attrs: kind)
- `arcnet.anomaly` (counter from Griffin; attrs: metric, agent_id, direction, severity — emitted **only** for true outliers)

### Logs (OTLP)
- Structured guard findings + agent lifecycle + signal deliveries, all carrying `trace_id`/`span_id` for correlation in SigNoz UI.

## SigNoz features we consume

- [x] **Dashboards ×3, imported as JSON** (`deploy/provision/`):
  1. *Fleet Ops* — runs, latency, errors, active sessions
  2. *Threats & Trust* — threat counts by category/agent, block rate, guard latency, forward-facing exposure, recent findings (logs panel)
  3. *Cost & Tokens* — tokens + $ by agent/model, burn rate
  - ≥1 panel written in **ClickHouse SQL** (e.g. top attack subcategories from span events) — shows query-depth
  - JSON authored; `setup.py` validates + live-imports. **Phase 6 IDs:** Fleet Ops `019f8883-fc38-…`, Threats & Trust `019f8883-fc4a-…`, Cost & Tokens `019f8883-fc57-…`, Agno `019f8883-fc67-…`.
- [x] **Alert rules** (provisioned via API): threat>0 (1m), cost burn rate, tool-calls-per-session (loop), p99 latency, error rate, `arcnet.anomaly>0` (Griffin outliers). **Payloads must use the current v5 `queries` array format** — the legacy `builderQueries` map shape is rejected outright on modern SigNoz (maintainer-confirmed); author against the Terraform-provider examples, never from tutorial memory. **Record the evaluation interval and tune eval/`for:` windows in Phase 2** — on-camera self-correct rides the inline fast-path (`02` §3); the alert is the system of record and must land close behind it
  - Payloads in `deploy/provision/alerts.json` (v5 `queries` only). **Phase 6 pin note (v0.133):** live `POST /api/v1/rules` accepts the **flat** condition shape (`op`/`matchType` numeric codes `"1"`/`"2"` + top-level `preferredChannels`); nested `thresholds.spec` with named enums is rejected as `alert rule is not valid`. All six rules live (IDs `019f8886-6939-…` … `019f8886-6993-…`).
- [x] **Native anomaly-based alert** on ≥1 metric (SigNoz's built-in seasonal z-score alert type) — used alongside Griffin; README explains the pairing: SigNoz's seasonal model excels once history exists, Griffin (zero-shot TabFM) covers short-history agents from their first minutes. **Its evaluation windows are ≥5m by design — it can never fire live on camera**; it's a configured-rule + pre-seeded-history screenshot artifact, and the demo never pretends otherwise
  - Artifact: `deploy/provision/alert-seasonal-anomaly.json` — provisioned as `anomaly_rule` id `019f8886-69a6-…`.
- [x] **Webhook notification channel** → `POST /webhooks/signoz` (alert payload: grouped alerts, `fingerprint` for dedupe, `endsAt` for resolution — handle both firing + resolved)
  - Server route live; channel `arcnet-webhook` id `019f8883-fc29-…`. Phase 6 re-verified: firing payload → HTTP 204 → attributable `steer`/`critical` signal (`sig_c7a53831` on `s_0c6b0aa6` / `agent_j`).
- [x] **Query Range API** (`POST /api/v5/query_range`, key auth) — powers the ArcNet UI (Fleet Health, threat feed) and Case File evidence. (Time Machine transcripts are **SQLite-primary** — spans carry summaries + pointers, not full tool outputs; `10-time-machine.md`.)
  - **Phase 6:** authenticated Query Range 200 against seeded `arcnet-hello` trace `68a0c4a9b793b111882557834a98f57b` (spans: `hello_arcnet.run` / `OpenAIChat.invoke` / `add` / `OpenAIChat.invoke`). `/api/signoz/status` → `api_key_present=true`, `query_range_ok=true`.
- [ ] **Griffin metric discovery** — **default = a hardcoded allowlist of the `arcnet.*` counters we emit ourselves** (`arcnet.threats.detected`, `arcnet.cost.usd`, `arcnet.tool.calls`, `arcnet.guard.latency`, `arcnet.tokens.total`): no documented metrics-listing endpoint exists on the Query Range API, and `gen_ai.*` metrics don't exist in this pipeline at all. Auto-discovery (metrics metadata API or MCP `signoz_list_metrics`) is a stretch goal, not the plan.
- [ ] **Trace deep-links** from the ArcNet UI into SigNoz trace view (judges see native UI too)
- [x] **Agno dashboard template** fetched into `deploy/provision/agno-dashboard.json` (from SigNoz/dashboards `agno/agno-dashboard.json`). Import via UI (Dashboards → Import) or Phase 2 `setup.py`; do not author custom panels until against the live keys above.

## SigNoz AI surface (docs/ai/*) — use all of it that works self-hosted

- [~] **SigNoz MCP server** (self-hosted binary/Docker; 40+ tools: `signoz_get_trace_details`, `signoz_search_logs`, `signoz_aggregate_traces`, `signoz_create_alert`, `signoz_import_dashboard`, `signoz_execute_builder_query`, …). Two roles:
  - **Dev-time**: wired into Cursor/Claude Code while building — author dashboards/alerts/queries with it, then freeze the JSON into `deploy/provision/`.
  - **Demo-time (Case File beat)**: case files embed `trace_id`s + instructions; the coding agent pulls live evidence via MCP and fixes the agent. Mirrors SigNoz's own "reconstruct a bug from a trace ID" / "postmortem evidence pack" use cases, specialized for agent security — name-check that in the README.
  - **Phase 2:** `deploy/mcp/install.sh` installs **v0.8.0**; Cursor/Claude configs in `deploy/mcp/`. Stdio needs `SIGNOZ_API_KEY`.
  - **Phase 6 G5:** binary present + key wired; headless stdio MCP session hung (OTEL metrics exporter noise + framing). **Fallback used:** Case File export (`/export/case-file/{id}`) + Query Range curl against known `trace_id` (hello + threat session handoff pack). Human IDE MCP connect still recommended for on-camera beat.
- [~] **SigNoz agent skills** installed in the dev agent (`/plugin marketplace add SigNoz/agent-skills` → `/plugin install signoz@signoz-skills`): generating-queries, writing-clickhouse-queries, creating-dashboards, creating-alerts, investigating-alerts. Documented in README as part of our workflow (judges appreciate dogfooding their AI tooling).
  - Steps in `deploy/mcp/README.md` (human IDE install).
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
