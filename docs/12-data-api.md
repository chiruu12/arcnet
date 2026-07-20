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
```

**Not tables (deliberate):** Case Files are generated on demand from `sessions` + `threats` + `replays` — no storage. Griffin's forecasts live in the worker's in-memory cache (the UI band renders the last cycle; anomalies land in SigNoz as telemetry and here as `signals` with `source='griffin'`).

## API contract (FastAPI · all JSON · no auth, localhost demo surface)

| Route | In | Out |
|---|---|---|
| `GET /api/fleet` | — | `[{agent_id, name, role, exposure, model, last_seen, health: {sessions_24h, threats_24h, blocked_24h, cost_24h_usd, anomalies_24h, active_signals}}]` |
| `GET /api/threats?since=&agent_id=` | query | `[threat row]` (newest first, cap 200) |
| `GET /api/sources?agent_id=&session_id=` | query | `[source row]` |
| `GET /api/sessions/{id}?include=transcript` | path | session row (+ full transcript only when asked — it's big) |
| `POST /api/replay` | `{session_id, candidate_model?, candidate_prompt?}` (exactly one candidate) | the verdict object (`10`) — synchronous; progress streams over SSE |
| `POST /api/replay/corpus` (P1) | `{candidate_model}` | scorecard aggregate |
| `GET /api/agent-view/{view}/{id}` | `view ∈ incident, fleet, session, replay, sources` | agent-view envelope (below) |
| `POST /api/signal` | Signal fields minus id/status (used by the SDK inline fast-path AND the UI's manual pause/kill buttons) | created signal row |
| `GET /signals/stream?session_id=` | query (omit = firehose) | SSE (events below) |
| `POST /webhooks/signoz` | SigNoz alert payload | 204 |
| `POST /api/hitl/{hitl_id}` | `{decision: "approved"\|"rejected"}` | updated row (server relays to AgentOS) |
| `GET /export/case-file/{session_id}` | path | zip: `case-file.md` + `case-file.json` |

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
