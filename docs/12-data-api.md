# Data & API Contract (v1)

The server's SQLite schema and every API/SSE shape, **frozen before build** so `sdk/`, `server/`, `hq/`, and every Cursor session code against the same contract. If a shape here conflicts with prose elsewhere, this doc wins for wire/storage detail; `10-time-machine.md` wins for replay semantics.

## Conventions

- **IDs**: prefixed short ids — `s_` session · `r_` replay · `sig_` signal · `thr_` threat · `src_` source · `hitl_` approval (8 hex chars from `secrets.token_hex(4)`).
- **Time**: APIs speak ISO-8601 UTC strings; the DB stores INTEGER epoch-milliseconds.
- **JSON columns** are TEXT holding JSON documents (SQLite JSON1 available for queries).
- **SQLite setup**: WAL mode (SSE readers + one writer), `CREATE TABLE IF NOT EXISTS` at server boot. **No migration tool in v1** — schema changes wipe + reseed; all demo data is regenerable by the runner. (Post-v1: real migrations.)
- **Product-core rule** (`02`): these are product tables. Nothing scenario-specific — scenarios exist only as the nullable `sessions.scenario` label; a live-work agent's sessions use the same tables with `scenario = NULL`.

## Schema

```sql
CREATE TABLE IF NOT EXISTS agents (
  agent_id    TEXT PRIMARY KEY,                 -- "agent_j"
  name        TEXT NOT NULL,
  role        TEXT,                             -- "support/ops"
  exposure    TEXT NOT NULL DEFAULT 'internal', -- forward_facing | internal
  model       TEXT,
  first_seen  INTEGER,
  last_seen   INTEGER
);
-- upserted by the server on first telemetry/heartbeat from any arcnet.init() agent

CREATE TABLE IF NOT EXISTS sessions (
  session_id        TEXT PRIMARY KEY,
  agent_id          TEXT NOT NULL REFERENCES agents(agent_id),
  scenario          TEXT,                       -- "S1" | NULL (live work)
  goal              TEXT,
  system_prompt_ref TEXT,                       -- "agents/prompts/j.md@<sha>"
  model             TEXT,
  temperature       REAL,
  status            TEXT NOT NULL,              -- running | completed | killed | failed
  outcome           TEXT,                       -- json {goal_reached, exfil_attempts, steps, tool_errors}
  usage             TEXT,                       -- json {input_tokens, output_tokens, cost_usd, latency_ms}
  trace_id          TEXT,
  transcript        TEXT,                       -- json: full replay-ready transcript (10-time-machine.md)
  agent_version     TEXT,                       -- optional registered version tag (HQ Agent / docs/18)
  started_at        INTEGER,
  ended_at          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id, started_at);
```

**Deliberate choice:** the transcript is one JSON document, not a normalized steps table — replay always reads it whole, the UI renders it whole, and a steps table buys nothing at v1 scale. Revisit post-v1 if transcripts need querying.

```sql
CREATE TABLE IF NOT EXISTS signals (
  signal_id    TEXT PRIMARY KEY,
  session_id   TEXT,
  agent_id     TEXT NOT NULL,
  kind         TEXT NOT NULL,                   -- steer | pause | kill | note
  severity     TEXT NOT NULL,                   -- info | warn | critical
  reason       TEXT NOT NULL,
  evidence_link TEXT,
  guidance     TEXT,
  source       TEXT NOT NULL,                   -- inline | alert | griffin | manual
  status       TEXT NOT NULL DEFAULT 'pending', -- pending | delivered | acted | expired
  created_at   INTEGER,
  delivered_at INTEGER
);

CREATE TABLE IF NOT EXISTS threats (
  threat_id   TEXT PRIMARY KEY,
  session_id  TEXT,
  agent_id    TEXT,
  checkpoint  TEXT,                             -- input | retrieved | tool_call | output
  action      TEXT,                             -- allow | redact | block | review
  category    TEXT,                             -- injection | leakage | destructive | ...
  subcategory TEXT,                             -- rule id, e.g. "ignore_previous"
  risk_score  REAL,
  trust_level TEXT,
  evidence    TEXT,                             -- SHORT excerpt only, never full content
  trace_id    TEXT,
  span_id     TEXT,
  created_at  INTEGER
);

CREATE TABLE IF NOT EXISTS sources (
  source_id   TEXT PRIMARY KEY,
  session_id  TEXT,
  agent_id    TEXT,
  origin      TEXT,                             -- url | tool name | "user"
  trust_level TEXT,                             -- user | retrieved | scraped | tool_output | external | system
  scan_action TEXT,                             -- allow | redact | block | review
  findings    INTEGER DEFAULT 0,
  created_at  INTEGER
);
-- the ingested-source ledger: feeds Sources & Trust AND the deferred context inspector —
-- the DATA is captured from day 1 even though that UI comes later (user call)

CREATE TABLE IF NOT EXISTS replays (
  replay_id            TEXT PRIMARY KEY,
  session_id           TEXT NOT NULL REFERENCES sessions(session_id),
  candidate_model      TEXT,
  candidate_prompt_ref TEXT,
  runs                 TEXT,                    -- json: raw per-run results (3-run majority evidence)
  verdict              TEXT NOT NULL,           -- json: the verdict object (10-time-machine.md)
  created_at           INTEGER,
  duration_ms          INTEGER
);

CREATE TABLE IF NOT EXISTS hitl_requests (
  hitl_id     TEXT PRIMARY KEY,
  run_id      TEXT NOT NULL,
  session_id  TEXT,
  payload     TEXT,                             -- json: what needs approval (tool call, content)
  status      TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | expired
  created_at  INTEGER,
  decided_at  INTEGER
);

CREATE TABLE IF NOT EXISTS webhook_events (
  fingerprint TEXT,                             -- SigNoz alert fingerprint (dedupe key)
  status      TEXT,                             -- firing | resolved
  payload     TEXT,                             -- raw json, kept for audit
  received_at INTEGER,
  PRIMARY KEY (fingerprint, received_at)
);

-- Additive (HQ Agent / docs/18): agent code+model timeline
CREATE TABLE IF NOT EXISTS agent_versions (
  version_id     TEXT PRIMARY KEY,              -- av_<hex>
  agent_id       TEXT NOT NULL REFERENCES agents(agent_id),
  version        TEXT NOT NULL,                 -- semver or opaque tag
  model          TEXT,
  model_version  TEXT,
  source_ref     TEXT,                          -- git sha / prompt@sha / image digest
  notes          TEXT,
  created_at     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_agent_versions_agent ON agent_versions(agent_id, created_at DESC);
```

**Additive session column (nullable):** `sessions.agent_version TEXT` — optional link to a registered version tag when known.

**Not tables (deliberate):** Case Files are generated on demand from `sessions` + `threats` + `replays` — no storage. Griffin's forecasts live in the worker's in-memory cache (the UI band renders the last cycle; anomalies land in SigNoz as telemetry and here as `signals` with `source='griffin'`). Model-change **proposals** are `signals` with `source='hq_agent'` / `kind='note'` — not a separate table in slice 1.

## API contract (FastAPI · all JSON · no auth, localhost surface)

| Route | In | Out |
|---|---|---|
| `GET /api/fleet` | — | `[{agent_id, name, role, exposure, model, last_seen, health: {sessions_24h, threats_24h, blocked_24h, cost_24h_usd, anomalies_24h, active_signals}}]` |
| `GET /api/threats?since=&agent_id=&limit=&offset=` | query | `[threat row]` (newest first; default cap 200). Headers: `X-Total-Count`, `X-Limit`, `X-Offset` (**additive**) |
| `GET /api/sources?agent_id=&session_id=&limit=&offset=` | query | `[source row]` + same pagination headers (**additive**) |
| `GET /api/sessions?scenario=&agent_id=&model=&limit=&offset=` | query | session index rows + `has_transcript`; **no** transcript. `model` filter **additive**. Pagination headers **additive** |
| `GET /api/sessions/{id}?include=transcript` | path | session row (+ full transcript only when asked — it's big) |
| `GET /api/agents/{agent_id}/models` | path | `[{model, session_count, latest_started_at}]` — distinct models for cascade pickers (**additive**) |
| `GET /api/signals?session_id=&agent_id=&source=&limit=&offset=` | query | `[signal row]` + pagination headers; `agent_id` / `source` filters **additive** |
| `GET /api/replays?session_id=&limit=&offset=` | query | replay index (no `runs` blob) + pagination headers (**additive**) |
| `POST /api/replay` | `{session_id, candidate_model?, candidate_prompt?}` (exactly one candidate) | the verdict object (`10`) — synchronous; progress streams over SSE |
| `POST /api/replay/corpus` (P1) | `{candidate_model}` | scorecard aggregate |
| `GET /api/agent-view/{view}/{id}` | `view ∈ incident, fleet, session, replay, sources, signals, check` | agent-view envelope (below). **`signals` + `check` additive** |
| `POST /api/signal` | Signal fields minus id/status (used by the SDK inline fast-path AND the UI's manual pause/kill buttons) | created signal row |
| `GET /signals/stream?session_id=` | query (omit = firehose) | SSE (events below) |
| `POST /webhooks/signoz` | SigNoz alert payload | 204 |
| `POST /api/hitl/{hitl_id}` | `{decision: "approved"\|"rejected"}` | updated row (server relays to AgentOS) |
| `GET /export/case-file/{session_id}` | path | zip: `case-file.md` + `case-file.json` |
| `GET /api/signoz/status` | — | `{signoz_url, ui_reachable, api_key_present, query_range_ok, query_note, dashboards: {fleet_ops, threats_trust, cost_tokens, agno}}` — dashboard ids from `SIGNOZ_DASHBOARD_*` env or title resolve (**additive** `dashboards`) |
| `GET /api/agents/{agent_id}/versions?limit=&offset=` | path + page | `[agent_version row]` + pagination headers (**additive** HQ Agent) |
| `POST /api/agents/{agent_id}/versions` | `{version, model?, model_version?, source_ref?, notes?, session_id?}` | created version row; optional `session_id` pins `sessions.agent_version` to the new `version_id` (**additive**) |
| `GET /api/agents/{agent_id}/versions/timeline` | path | `{agent_id, versions[], current_model?}` (**additive**) |
| `POST /api/agents/{agent_id}/apply-model` | `{confirm: true, model, version, model_version?, source_ref?, notes?, session_id?, proposal_signal_id?}` | bumps `agents.model`, registers version, optional session pin + marks proposal `status=applied`. **Requires `confirm: true`** (human-gated; **additive**) |

**Pagination convention (additive, 2026-07-22):** list bodies remain JSON **arrays** so existing HQ/clients keep working. Clients that need totals read `X-Total-Count` (and echo `X-Limit` / `X-Offset`). `offset` defaults to `0`; `limit` keeps prior defaults/caps.

**HQ hash deep-links (additive, product surface):** `#view` with optional `?agent=&model=&session=` (e.g. `#case_files?agent=agent_j&model=gpt-4o-mini&session=s_ecfdb55d`).

**SDK session tools (additive client):** `arcnet.hq.check_session` / `signals_view` / `session_view` / `incident_view` / `sources_view` — thin wrappers over agent-view envelopes (no full tool dumps).

**HQ Agent tools (additive client, docs/18):** `arcnet.hq_tools` — `signoz_status`, `fleet_overview`, `agent_signals`, `session_check`, `case_file_view`, `replay_compare`, `griffin_anomalies` (MAD-labeled), `list_agent_models`, `recommend_models`, `agent_version_timeline`, `register_agent_version` (optional `session_id` pin), `propose_model_change`, `list_model_proposals`, `apply_model_change` (requires `confirm=True`). Proposals write `signals` with `source=hq_agent`; apply is human-gated.

### Agent-view envelope (every view, same wrapper)

```json
{
  "view": "incident",
  "id": "s_f3a9",
  "generated_at": "2026-07-24T18:02:11Z",
  "data": { "…view-specific, goal-level, trust-annotated…": "…" },
  "links": {
    "human_view": "/sessions/s_f3a9",
    "signoz_trace": "http://localhost:8080/trace/<trace_id>",
    "self": "/api/agent-view/incident/s_f3a9"
  },
  "hints": {
    "raw_evidence": "SigNoz MCP: signoz_get_trace_details(trace_id='<trace_id>'), signoz_search_logs(...)"
  }
}
```

`data` for `incident`: `{goal, agent, exposure, root_cause: {checkpoint, trust_level, category, evidence_excerpt}, outcome, recommended_actions[], related_replay_id}`. For `replay`: the verdict object. For `fleet`/`session`/`sources`: the same rows the human view renders, minus presentation.

**Additive agent views:**

- `signals` (`id` = `agent_id` or `session_id`): `{signals: [{signal_id, kind, severity, reason_excerpt, guidance_excerpt, source, status, session_id, agent_id, created_at}], truncated}` — excerpts only.
- `check` (`id` = `session_id`): compact session inspection `{session: {…meta…}, counts: {threats, signals, sources, timeline_steps}, top_threat, active_signals: […bounded…], links}` — no full tool outputs.

### SSE events (`/signals/stream`)

`event:` one of `signal` · `threat` · `replay_progress` · `hitl_request`; `data:` = the corresponding row/object as JSON. `replay_progress`: `{replay_id, step, total_steps, phase: "loading"|"replaying"|"diffing"}`. Client reconnects with `Last-Event-ID`; server replays missed rows from the tables (that's why signals/threats persist).

### Webhook handling (`/webhooks/signoz`)

Store raw event → dedupe on `fingerprint` within a 5m window → map alert labels (`session_id`, `agent_id`, `arcnet_kind`) to a Signal (`source='alert'`) → same bus as the inline path. Handle both `firing` and `resolved` (resolved → mark related signal `expired`). Labels are set at provision time (`04`).

### Case File bundle

`case-file.md`: summary → root cause (with trust provenance) → timeline excerpt → recommended actions → **fix-prompt preamble** (instructions addressed to the coding agent, incl. the MCP hint block). `case-file.json`: the `incident` agent-view envelope verbatim. Everything a coding agent needs offline; MCP pointers for live evidence.

## Who writes what (ownership, so parallel work doesn't collide)

- **SDK** (in-process): emits telemetry; POSTs `/api/signal` (inline fast-path); consumes SSE per-session.
- **AgentOS callback / SDK run-end hook**: writes `sessions` (transcript at run end; `running` row at start).
- **Server**: owns `signals`, `threats`, `sources`, `replays`, `hitl_requests`, `webhook_events`, `agents` upserts; guard checkpoint events arrive piggybacked on the SDK's signal-client channel (batched POST, v1-simple).
- **UI**: reads REST + SSE only; never writes except `/api/signal` (manual) and `/api/hitl/*`.
