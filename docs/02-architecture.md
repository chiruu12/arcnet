# ArcNet — Architecture

## System overview

```mermaid
flowchart LR
    subgraph Agents["agents/ — Agno fleet (AgentOS runtime)"]
        J["Agent J<br/>(support/ops agent)"]
        K["Agent K<br/>(second fleet member)"]
        BS["Bug Suite<br/>scenario runner"]
        BS --> J
    end

    subgraph SDK["sdk/ — arcnet SDK (in-process)"]
        INST["OTel setup +<br/>openinference-instrumentation-agno"]
        GUARD["UnplugGuardrail + tool hooks<br/>(unplug-ai)"]
        SIG["Signal client<br/>(SSE subscribe)"]
    end

    J --- SDK
    K --- SDK

    SIGNOZ["SigNoz (self-hosted Docker)<br/>OTLP · ClickHouse · dashboards · alerts"]
    MCP["SigNoz MCP server<br/>(self-hosted binary/Docker)"]
    SERVER["server/ — arcnet-server (FastAPI)<br/>signal bus · query proxy · Griffin<br/>agent-view API · Time Machine (replay)"]
    HQ["hq/ — ArcNet UI<br/>(React · product-grade)"]
    CODER["Coding agent<br/>(Cursor / Claude Code / Codex)"]

    INST -- "OTLP traces/metrics/logs" --> SIGNOZ
    GUARD -- "trust spans + threat metrics" --> INST
    SIGNOZ -- "alert webhook" --> SERVER
    SERVER -- "signals (SSE)" --> SIG
    SIG -- "pause / steer / cancel" --> J
    SERVER -- "Query Range API (read traces)" --> SIGNOZ
    SERVER -- "replay recorded session<br/>vs candidate model" --> J
    HQ -- "REST + SSE" --> SERVER
    HQ -. "deep links" .-> SIGNOZ
    SERVER -- "agent-view JSON + Case File" --> CODER
    CODER -- "signoz_get_trace_details, search_logs…" --> MCP
    MCP --> SIGNOZ
```

## Framework decision: Agno

Demo agents run on **Agno** (we know it well; it's also the cleanest integration surface):

- **Instrumentation is first-class**: SigNoz has an official Agno guide using `openinference-instrumentation-agno`, and SigNoz ships a **prebuilt Agno dashboard template** — we import it day 1 and build our custom dashboards alongside it.
- **Guardrail framework**: Agno supports pre/post hooks + a `BaseGuardrail` class. Unplug integrates as `UnplugGuardrail` — idiomatic Agno, not bolted-on middleware. (Post-hackathon this doubles as an OSS contribution candidate to Agno.)
- **Tool hooks**: per-tool pre/post interception → `guard.check_tool_call()` + taint checks exactly where they belong.
- **HITL built in**: paused runs surface approval requests over a live socket → our `pause` signal becomes a real approve/reject flow driven from the UI.
- **Run cancellation** → `kill` signal. **AgentOS** (Agno's FastAPI runtime) serves the fleet → the UI triggers scenario runs over HTTP, sessions/state come free.

## Data flows

### 1. Telemetry (always on)
`AgnoInstrumentor().instrument()` + OTel SDK (traces/metrics/logs → OTLP → SigNoz). Agent runs emit agent/LLM/tool spans; we add `arcnet.guard` spans at checkpoints, threat counters, and finding logs. Token/cost metrics: derive OTel counters from Agno's per-run metrics (verify exact field names day 1) so the Cost dashboard has real numbers.

### 2. Inline defense — source-trust monitoring (ms)
Unplug is the **provenance/trust spine**. Every ingested datum is tagged with a trust level; the untrusted ones get scanned. Implemented the Agno way:
- **pre-hook / input guardrail** → `guard.scan(text, source=USER)`
- **tool post-hook on fetch/retrieval tools** → `guard.scan(text, source=RETRIEVED)` + `wrap_for_context()` + `notify_taint_source()` — **scraped/fetched content filtered before it reaches the model**
- **tool pre-hook (all tools)** → `guard.check_tool_call(name, args)` (taint propagation → block untrusted content flowing to sensitive tools)
- **output guardrail / post-hook** → `guard.scan_output(text)` (secrets/PII → redact)

`ScanResult.action` drives behavior: `allow` → proceed; `redact` → substitute `redacted_text`; `block` → raise guardrail error (span status ERROR); `review` → proceed + flag. **Every result — including clean ones — becomes telemetry.** Each agent carries an `arcnet.exposure` attribute (`forward_facing` | `internal`) derived from whether it ingests third-party content; forward-facing agents are surfaced as higher injection-risk in the Fleet Health view.

### 3. Reactive signals (seconds)
SigNoz alert rule fires (threat count, cost burn, loop depth, p99 latency) → webhook POST `server/webhooks/signoz` → server maps to the canonical **`Signal{session_id, agent_id, kind, severity, reason, evidence_link, guidance}`** (this exact shape is the contract used everywhere — SDK, server, plan) → SSE. SDK signal client checks the per-session queue inside tool hooks (between steps):
- `steer` → inject corrective guidance into the run's context, continue
- `pause` → trigger Agno HITL pause; the UI shows approve/reject; resume on decision
- `kill` → cancel the run
- `note` → annotate telemetry only

Signals also stream to the UI's live feed.

### 4. Agent-view + hand-off (the machine-optimal twin)
Every ArcNet view has a paired **agent-view**: `GET /api/agent-view/{view}/{id}` returns a goal-level, trust-annotated, structured JSON — not raw logs. For an incident it carries: root cause (where + trust level + finding), the recorded outcome, recommended actions, and a `signoz:` trace pointer. The **Case File** is the packaged bundle of the same (`case-file.md` + `case-file.json` + embedded `trace_id`s + fix-prompt preamble). A coding agent (Claude Code / Codex / Cursor) reads the agent-view/Case File, pulls raw evidence itself via the **SigNoz MCP server** (`signoz_get_trace_details`, `signoz_search_logs`), and patches the observed agent. Mirrors SigNoz's own "reconstruct a bug from a trace ID" / "postmortem evidence pack" MCP use cases, specialized for agent trust.

### 5. Time Machine — counterfactual replay (the proof)
`POST /api/replay {session_id, candidate_model | candidate_prompt}`:
1. **Load** the recorded session from SigNoz traces (Query Range API): the ordered steps — user goal, each tool call and its **recorded output**, each model turn.
2. **Replay** the agent with tool outputs **mocked** from the trace (the replay harness intercepts Agno tool calls and returns the recorded result) so the *only* variable is the model/prompt. Runs against the candidate through the same `UnplugGuardrail` (so trust checks apply identically).
3. **Diff** the trajectories → `{resisted_injection, exfil_attempts, goal_reached, cost, latency, tokens}` for baseline vs candidate.
4. **Verdict + recommendation** → surfaced in the Time Machine view and available as agent-view JSON for a coding agent to act on. Optionally loop over a corpus of recorded incidents ("candidate resists 10/12").

This is **replay-from-trace, not live re-execution** — deterministic, cheap (one model call per step, no real tools), and demoable. It reuses the traces SigNoz already stores; no new datastore.

## Components

### `sdk/` — Python package `arcnet`
- `arcnet.init(service_name, session_id, otlp_endpoint, guard_config)` — OTel providers (traces+metrics+logs), `AgnoInstrumentor`, Guard construction, signal subscription.
- `arcnet/guardrail.py` — `UnplugGuardrail` (Agno guardrail) + tool hook factories; emits spans/metrics/logs; maps `Action` → control flow.
- `arcnet/signals.py` — SSE client, per-session queue, `check_signals()` hook, HITL/cancel helpers.
- `arcnet/replay.py` — replay harness: wraps an Agno agent so tool calls return recorded outputs (from a trace) instead of executing; used by the Time Machine.
- Telemetry namespace `arcnet.*`: see `04-signoz-integration.md`.

### `agents/` — demo fleet + Bug Suite
Agents J & K on **AgentOS** (single FastAPI app). Agent J: support/ops agent. Tools: `fetch_url` (injection vector), `lookup_customer` (seeded PII), `send_email` (exfil vector), `run_query` (destructive vector). Agent K: minimal second fleet member so the board isn't lonely. Model: cheap + fast (gpt-4o-mini or haiku — decide day 1 by keys; cost telemetry needs real tokens).

Bug Suite scenarios (`agents/scenarios/`), each = seeded fixture + script + expected detections:
| # | Codename | Attack | Expected chain |
|---|---|---|---|
| S1 | **Edgar** | Indirect injection in fetched page → email exfil attempt | retrieved-scan flags → taint → tool pre-hook **block** → alert → signal `steer` → agent self-corrects |
| S2 | **Neuralyzer** | Output contains PII/secret from DB | output guardrail → **redact** → UI flash |
| S3 | **Serleena** | Injected destructive tool call (`DROP TABLE`) | tool pre-hook **block** |
| S4 | **The Worms** | Runaway loop / token burn | SigNoz metric alert → signal `kill` (cancel run) |
| S5 | **Frank** | Direct jailbreak/DAN in user input | input guardrail **block** (fast path) |
| S0 | Baseline | Clean run | all green — contrast shot |

Seeds: unplug-ai's built-in labeled samples + hand-written indirect-injection page fixtures (llmail-inject style).

### `server/` — FastAPI
Routes: `/webhooks/signoz`, `/signals/stream` (SSE per-session + firehose), `/api/fleet`, `/api/threats`, `/api/sources` (source-trust ledger), `/api/sessions/{id}`, `/api/agent-view/{view}/{id}` (machine-optimal twin of every view), `/export/case-file/{id}`, `/api/replay` (Time Machine), `/api/signal` (manual signal from the UI — pause/kill buttons), `/api/hitl/{run_id}` (approve/reject → AgentOS). State: SQLite. SigNoz access: Query Range API with service-account key (server-side only). Triggers scenario + replay runs by calling AgentOS.

Also hosts **Griffin** (`server/griffin.py`, async worker): FM-powered metric anomaly detection — pulls metric history from the Query Range API every 60s, forecasts expected bands with Google TabFM (zero-shot regression + split-conformal residuals), and emits `arcnet.anomaly` telemetry only for true outliers, which rides the existing alert→webhook→signal path. Design: `07-griffin-anomaly.md`.

### `hq/` — React + Vite + Tailwind (product-grade; direction in `09-frontend.md`)
Views (IA per v2):
- **Fleet Health** — agents + trust posture (forward-facing flagged) + threats + cost + Griffin anomalies.
- **Time Machine** (the star) — pick a recorded session, choose a candidate model/prompt, run the replay, see the side-by-side behavioral diff + verdict.
- **Sources & Trust** — per-agent ledger of ingested sources, trust levels, what Unplug filtered/blocked.
- **Signals** — live feed (incl. HITL approve/reject).
- **Case Files** — preview + download + "hand to coding agent" instructions.
- **Global Human ⇄ Agent view toggle** — every view flips to its agent-view JSON (the machine-optimal twin).

The UI never **queries SigNoz's API** directly — all telemetry comes through the arcnet-server proxy so the service-account key stays server-side. The only exception is deep-link hyperlinks that *open the SigNoz UI in a new tab* (no API call, no key).

### `deploy/`
- `docker-compose.yaml` — SigNoz self-host, pinned version.
- **SigNoz MCP server** — self-hosted binary (darwin_arm64) or Docker; wired into Cursor/Claude Code config. Used two ways: **dev-time** (we build dashboards/alerts/queries with SigNoz agent skills + MCP while developing) and **demo-time** (the Case File beat).
- `provision/` — idempotent setup: import Agno dashboard template + our 3 custom dashboards, alert rules, webhook channel. Prefer plain SigNoz APIs in the script; use MCP/agent-skills interactively to author the JSON.

## Repo layout

```
arcnet/
├── README.md
├── docs/
├── deploy/
│   ├── docker-compose.yaml      # SigNoz
│   ├── mcp/                     # SigNoz MCP server setup + client configs
│   └── provision/               # dashboards JSON, alert rules, setup script
├── sdk/                         # python: arcnet (uv project) — init, guardrail, signals, replay harness
├── server/                      # python: arcnet-server (uv, depends on sdk) — signals, Griffin, agent-view, Time Machine
├── agents/                      # python: AgentOS app + bug suite (uv)
├── hq/                          # pnpm: react UI (Fleet Health · Time Machine · Sources & Trust · Signals · Case Files)
└── scripts/                     # run-demo.sh, seed.py, bring-up
```

Python 3.12+, `uv` workspaces. Pinned deps (versions verified on PyPI 2026-07-20 — pin these, re-resolve day 1): `unplug-ai==0.5.2` (requires-python ≥3.11), `agno==2.7.4` (v2 line = AgentOS), `openinference-instrumentation-agno==0.1.38`, `opentelemetry-sdk` + OTLP exporters, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-system-metrics`, model SDK (`openai` or `anthropic`), `fastapi`, `httpx`, `sse-starlette`; server extra: `tabfm` (git-pinned commit, no PyPI) with `tabpfn==8.1.0` as fallback. SigNoz MCP server: `signoz-mcp-server v0.8.0` (binary/Docker).

## Secrets & env surface

Enumerated so the "judge runs `docker compose up` + `run-demo.sh`" claim is real. All in `.env` (git-ignored); `.env.example` ships with every key documented.

| Var | Purpose | Who needs it |
|---|---|---|
| `OPENAI_API_KEY` *or* `ANTHROPIC_API_KEY` | Demo agent model (gpt-4o-mini vs haiku — pick Day 0 by which key the dev has) | agents/, sdk/ |
| `ARCNET_MODEL` | Which model id to use (drives `pricing.py` lookup) | agents/ |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP → SigNoz collector (self-host: `http://localhost:4318`) | sdk/ |
| `SIGNOZ_API_KEY` | Service-account key for Query Range API (server-side only) | server/ |
| `SIGNOZ_URL` | SigNoz instance URL | server/, MCP |
| `ARCNET_SERVER_URL` | Signal SSE + API base | sdk/, hq/ |
| `HF_TOKEN` | (only if TabFM/TabPFN weight download needs it) | server/ (Griffin) |

The **SigNoz MCP server** client config (Cursor `.cursor/mcp.json` / Claude Code) reuses `SIGNOZ_URL` + `SIGNOZ_API_KEY` — documented in `deploy/mcp/`. Model price constants (not a secret) live in `sdk/arcnet/pricing.py`.

## Key risks & mitigations

| Risk | Mitigation |
|---|---|
| SigNoz self-host heavy on the Mac (ClickHouse) | Pin versions, allocate Docker resources day 1; fallback = SigNoz Cloud (everything incl. MCP works there; would also unlock Noz) |
| `openinference-instrumentation-agno` gaps with current Agno version | Official SigNoz guide exists → low risk; day-1 smoke test; fallback manual OTel wrappers in guard hooks |
| Agno guardrail/HITL APIs drift (fast-moving framework) | Pin `agno` version day 1; we know the framework — verify hook signatures against the pinned version before building |
| `unplug-ai==0.5.2` API drift vs docs | Core contract verified; smoke-test day 1; pin |
| Query Range API shape on self-host | Verify day 2 before building export on it |
| Webhook payload lacks trace context | Encode session/agent identity into alert labels at provision time; server enriches via Query API |
| **Time Machine replay: recorded trace lacks full inputs to re-run** | We control the demo agents, so we record what the harness needs (goal, tool I/O, model turns) as span attributes at trace time — don't rely on reconstructing from generic OTel spans. Verify the recorded-session round-trip Day 3 before building the diff UI. Fallback: the harness replays from ArcNet's own SQLite session store, not SigNoz. |
| **Counterfactual result is nondeterministic (LLM sampling)** | Replay at temperature 0; run the candidate 3× and report the majority behavior if needed; the demo scenario is chosen so the behavioral gap is large and stable. |
| Solo + 6 days | P0 first; pre-agreed cut list in `03-plan.md` |
```
