# Phase 6 — API read models (human vs agent), Docker-free batch

Scope: separate the human (dashboard) and agent (machine-context) read models behind shared
query primitives, without touching any frozen `12-data-api.md` shape. Docker/SigNoz stay OFF;
anything needing them is DEFERRED, not failed.

## Contract principle

- **Human APIs** (HQ dashboards): stable typed rows/summaries per `12`, filterable, capped,
  presentation-ready (health aggregates, chart-friendly numbers). The UI renders them directly.
- **Agent APIs** (`/api/agent-view/*`, Case File): incident/session-centric evidence with causal
  timeline, IDs + links, recommended actions, MCP hints — **bounded**: no full tool outputs, no
  secrets; short excerpts + evidence pointers instead (matches the `threats.evidence` rule).
- **Sharing**: one repository module owns SQL and returns domain records; separate serializers
  (read models) project them for each audience. No endpoint calls another endpoint over HTTP;
  routes stay thin.

## Endpoint inventory matrix

| Dashboard endpoint (human) | Consumer / purpose | Agent twin | Shared primitive | Status |
|---|---|---|---|---|
| `GET /api/fleet` | Fleet Health cards | `GET /api/agent-view/fleet/all` | fleet-health aggregate query | exists — but N+1 inline SQL, no shared primitive; agent twin wraps the human payload (per `12`: same rows minus presentation) |
| `GET /api/sessions` (list) | Time Machine picker, Case Files picker | — (list is human-only; agent side is per-id) | sessions query | exists — additive endpoint, needs validation + deterministic ordering |
| `GET /api/sessions/{id}?include=transcript` | session detail / replay loader | `GET /api/agent-view/session/{id}` | session fetch | **wrong** — agent view returns the FULL transcript incl. complete recorded tool outputs; must become a bounded evidence timeline (constraint: no full tool outputs in agent contexts) |
| `GET /api/threats` | Fleet Health / threat feed | folded into `incident` root-cause | threats query | exists — inline SQL; root-cause picker shared via repository |
| `GET /api/sources` | Sources & Trust table | `GET /api/agent-view/sources/{id}` | sources query | exists — two different inline queries (params vs OR-match); unify; unknown id should 404, not `[]` |
| `GET /api/signals` | Signals feed (initial load) | — (`signal` rows stream over SSE) | signals query + session-attribution rule | **wrong** — REST `?session_id=` excludes fleet-wide (NULL-session) rows while the SSE live filter and reconnect catch-up include them; extract one attribution predicate |
| `GET /signals/stream` (SSE) | Signals live feed + SDK | same stream | same attribution predicate | exists — catch-up query moves to repository |
| `POST /api/replay` → verdict | Time Machine run | `GET /api/agent-view/replay/{id}` | replay row + verdict | exists — replay agent view builds its own envelope; unify on the shared envelope builder |
| `GET /api/replays` (list) | Time Machine history | — | replays query | exists — inline SQL; normalize |
| Case Files view (uses incident view) | Case File preview | `GET /api/agent-view/incident/{id}` + `GET /export/case-file/{id}` | incident read model (root cause, related replay, actions) | exists — already shared with the exporter; move to read-model module |
| `GET /api/mock/time-machine` | none (Phase 3 shell leftover) | — | — | **remove** — dead, unconsumed, not in `12` |

Write-side routes (`POST /api/agents|sessions|threats|sources|signal|hitl`, webhook) are already
thin per `12` ownership; their SQL moves to the repository unchanged.

## docs/12 conflicts (frozen — documented, not mutated)

1. **Timestamps**: `12` says APIs speak ISO-8601; the shipped implementation returns DB
   epoch-milliseconds in every row (HQ's `ts()` and the SDK depend on it). Envelope
   `generated_at` is ISO. Converting now would break every consumer for zero demo value —
   **documented drift, no change** (post-v1 with a versioned API).
2. **Session agent-view payload**: `12` says fleet/session/sources agent views carry "the same
   rows the human view renders, minus presentation". The human session row excludes the
   transcript by default, so bounding the agent view is contract-*restoring*, and the standing
   "no full tool outputs in agent contexts" rule wins. Additive fields (`timeline`,
   `evidence pointers`) live inside `data`, which `12` leaves view-specific.
3. Everything else is additive (list endpoints, internal refactor) or removal of a
   never-contracted mock route.

## Implementation order

1. `server/arcnet_server/repository.py` — all SQL (reads + writes) as functions returning
   domain records; deterministic ordering (`created_at DESC, id DESC`; fleet by
   `last_seen DESC, agent_id`); one `signals_for_session` attribution predicate (session rows +
   fleet-wide NULL rows) used by REST and SSE catch-up.
2. `server/arcnet_server/read_models.py` — human projections (fleet health payload) and agent
   projections (envelope builder, incident data, bounded session timeline, sources/fleet
   context, Case File markdown). Bounds: excerpts ≤ 200 chars, timeline keeps step order +
   guard/trust annotations + output length, never raw `recorded_output`.
3. `main.py` becomes thin routes: parse/validate (limit `1..500`), call repository + read
   model, raise 404s (`{"detail": …}` FastAPI shape, as today). Remove
   `/api/mock/time-machine`. Sources agent-view 404s when the id matches no agent/session.
4. Tests (`server/tests`): human vs agent projections differ intentionally over the same rows;
   transcript bounding (large recorded_output never appears in agent view / case file);
   pagination + filter validation; deterministic ordering tiebreaks; empty-DB shapes; missing-id
   404s; signal attribution REST == SSE catch-up.
5. `scripts/check_import_boundaries.py` — stdlib scan: `sdk/`, `server/`, `hq/` never import
   `agents/` or `scripts/`.

## Docker-free Phase 6 batch (after API work)

- LICENSE: none exists and no doc names one → Apache-2.0 (matches unplug-ai), holder from git
  author evidence (Chirag Gupta).
- README: judging-criteria map, model-boundary note (Unplug in-process, Griffin MAD with
  optional TabPFN worker, no vLLM), limitations + provenance, Docker-deferred steps explicit.
- Run the Docker-free demo end-to-end (seed → server → replay runtime → HQ → case-file export)
  with safe process cleanup.
- `docs/log.md`: 2-line phase note incl. the timestamp drift record.

**DEFERRED (Docker/SigNoz off):** G5 live MCP handoff + backup capture, README screenshots,
dashboard/alert provisioning, SigNoz Query Range verification. **Not planned:** corpus replay
endpoint (pre-cut), signals agent-view (not in `12`'s view enum), speculative endpoints.

## Acceptance

- All server/sdk/agents tests green; `hq` typecheck+build green; `uv lock --check` green;
  boundary scan green; demo smoke (fleet, sessions, replay list, agent views, case-file zip,
  SSE) green without Docker.
- Frozen `12` routes byte-shape identical except: session agent-view bounded (documented above),
  sources agent-view 404 on unknown id, mock route removed.
