# ArcNet hardening (P11)

Adversarial packet P11 hardens the server against hostile input and concurrent
load. Two suites, both offline and deterministic:

- `server/tests/test_redteam_api.py` — malformed / oversized / injection inputs (P11-A)
- `server/tests/test_concurrency.py` — threading/async races (P11-B)

Write-auth (`ARCNET_WRITE_SECRET`, off by default) is documented in
`docs/32-deployment-notes.md` and applies to every mutating `POST` (P11-C).

---

## Concurrency & resilience (P11-B)

Stress-tests the shared SQLite connection, in-process SSE bus, Griffin worker
cache, replay orchestration, and lifespan teardown under concurrent load.

| Race / hazard | Verdict | Fix |
|---------------|---------|-----|
| Module-global `get_conn()` shared across FastAPI threadpool + Griffin TabFM daemon | **Risk** — sqlite3 connections are not thread-safe; concurrent `execute`/`commit` can interleave; `fetchone()` after `execute()` outside the lock reads torn cursor state | `_ThreadSafeConnection` proxy serializes `execute`/`commit`/`rollback`; SELECT cursors hold the lock until `fetchone`/`fetchall`; `PRAGMA busy_timeout=5000` (with existing WAL) |
| `get_conn()` lazy init from multiple threads | **Risk** — double init / torn connection | Double-checked lock (`_conn_init_lock`) around first `connect()` + `init_db()` |
| WAL / busy_timeout not configured | **OK (WAL)** / **Gap (timeout)** | `connect()` already sets `journal_mode=WAL`; P11-B adds `busy_timeout=5000` |
| `EventBus.publish` from sync routes + Griffin thread into `asyncio.Queue` | **Risk** — asyncio queues are not thread-safe; full queue removed subscriber | Switched to bounded `queue.Queue` (max 256); **drop-oldest** on overflow (newest retained); `threading.Lock` on subscriber list; SSE reads via `run_in_executor` |
| SSE subscriber starvation under fan-out | **OK** after bus fix | All subscribers receive each event when queues are not saturated; saturated queues drop oldest, not newest |
| Unsubscribe during `publish` | **Risk** — list mutation during iteration | Snapshot subscriber list under lock before fan-out; unsubscribe is lock-guarded |
| Connect/disconnect subscriber leak | **OK** | `unsubscribe` removes queue; tests assert `_subs` empty after 50 cycles |
| Griffin `_CACHE` mutated by `griffin_loop` / TabFM thread while HTTP reads `cache_snapshot` | **Risk** — readers could observe torn dict updates | `threading.RLock` around cache writes and `copy.deepcopy` snapshot reads |
| Two concurrent `POST /api/replay` for one session | **OK** — each call allocates its own `replay_id` and persists separate verdict rows | No code change; tests mock `execute_replay` and assert distinct `replay_id` / verdict / DB rows |
| Lifespan exit leaves Griffin task or TabFM daemon running | **Gap** — griffin cancelled but TabFM loop had no shutdown signal | `shutdown_background_workers(reason="lifespan_shutdown")` sets TabFM `degraded`; griffin task awaited after `cancel()` |

---

## API red-team (P11-A)

Offline adversarial suite. Every attack below is asserted; verdict is **safe**
(already OK), **fixed** (hole patched this packet), or **deferred** (known gap,
not attempted).

### 1. Malformed bodies

| Attack | Endpoints | Verdict |
|--------|-----------|---------|
| Non-JSON body (`not-json`, empty) | All `POST` JSON routes | **fixed** — `parse_json_object()` → 400 `{detail}` |
| JSON array / `null` instead of object | All `POST` JSON routes | **fixed** — 400 `body must be a JSON object` |
| Missing required fields (`agent_id`, `run_id`, signal fields) | `/api/agents`, `/api/sessions`, `/api/signal`, `/api/hitl` | **fixed** — 400 `missing required field(s): …` |
| Wrong types (int `agent_id`, array `reason`) | Write routes | **safe** — SQLite accepts or route returns 4xx; no 500 |
| Deeply nested JSON (depth 80) | `/api/sessions` transcript | **safe** — parses; bounded by transcript byte cap on write |

Webhook (`/webhooks/signoz`) was already hardened in Wave A — **safe** (regression guarded).

### 2. Path / param injection

| Attack | Verdict |
|--------|---------|
| `../`, URL-encoded traversal in `session_id` / `agent_id` / `view` / `hitl_id` | **safe** — literal SQLite lookup → 404; no filesystem read |
| SQL meta (`' OR 1=1--`, `;DROP TABLE`) in path or query | **safe** — parametrized `?` placeholders throughout `repository.py` |
| 10 KB-long ids | **safe** — 404; no OOM |
| Unicode / RTL override chars | **safe** — 404 or empty result |
| NUL bytes in path | **safe** — client URL layer rejects; server never reached |
| Case-file export with traversal id | **safe** — zip built from DB row only; 404 when missing |

### 3. Pagination abuse

| Attack | Routes | Verdict |
|--------|--------|---------|
| `limit` / `offset` negative, zero, `10**9`, non-numeric, float | All paginated `GET` lists | **safe** — FastAPI `Query(ge=, le=)` → 422 |
| Duplicate query params (`limit=5&limit=3`) | `/api/sessions` | **safe** — framework picks last value |

### 4. Oversized payloads

| Field | Cap | Verdict |
|-------|-----|---------|
| `transcript` (serialized JSON) | 1 MiB | **fixed** — 422 on write |
| `goal`, `evidence`, `reason`, `guidance` | 16 KiB chars | **fixed** — 422 on write |
| `hitl.payload`, `sources.findings_detail` | 64 KiB JSON | **fixed** — 422 on write |
| Agent-view `goal` echo | 200 chars excerpt | **fixed** — `agent_session_context` + `session_check_data` now excerpt |
| Case-file zip / incident envelope | excerpt caps | **safe** — already bounded (regression guarded) |
| Human `GET /api/sessions/{id}?include=transcript` | unbounded by design | **deferred** — docs/12 intentional; localhost-trust model |

5 MiB ingest attempts are rejected at the API layer; agent-view and case-file responses stay under excerpt caps.

### 5. Content-type / header abuse

| Attack | Verdict |
|--------|---------|
| Missing `Content-Type` | **safe** — `request.body()` + `json.loads` |
| Wrong charset (`iso-8859-1` on UTF-8 body) | **safe** — parses |
| Duplicate query params | **safe** |

### 6. Write-auth bypass (`ARCNET_WRITE_SECRET`)

| Attack | Routes | Verdict |
|--------|--------|---------|
| No header / wrong secret / empty header | Every mutating `POST` incl. `/api/agents`, `/api/sessions`, `/api/threats`, `/api/sources`, `/api/signal`, `/api/agents/{id}/versions`, `/api/agents/{id}/apply-model`, `/api/replay`, `/api/hitl`, `/api/griffin/evaluate` | **safe** — 401; no partial write (regression guarded) |
| Bearer vs `X-Arcnet-Write-Secret` | Same | **safe** — both accepted via `hmac.compare_digest` |
| Secret unset (default) | Same | **safe by design** — writes open; localhost-trust logged once at boot (see docs/32) |

### Deferred (not attempted this packet)

- **Auth on read paths** — localhost-trust by design; bind `127.0.0.1` + env secrets for deploy.
- **Request body size limit at ASGI layer** — app-level JSON caps only; reverse proxy should set `client_max_body_size`.
- **Rate limiting / slowloris** — out of scope for SQLite-primary v1.
- **Live-key paths** (AgentOS replay, SigNoz Query Range) — require env keys; offline tests mock or skip.
- **SSE stream abuse** — long-lived connection; no per-connection cap in v1.
- **Full transcript on human read API** — intentional A15 hatch; agent views stay bounded.

---

## Test suites

Run (3× for flake check):

```bash
uv sync --all-packages --all-groups && uv pip install pytest
.venv/bin/python -m pytest server/tests/test_concurrency.py server/tests/test_redteam_api.py server/tests/test_write_auth.py -q
```

Full server suite:

```bash
.venv/bin/python -m pytest server/tests -q
```

## Files changed (P11)

- `server/arcnet_server/validation.py` — JSON parse, required fields, size bounds (P11-A)
- `server/arcnet_server/write_auth.py` — optional shared-secret gate on mutating routes (P11-C)
- `server/arcnet_server/bus.py`, `db.py`, `griffin.py` — thread-safe bus / connection / cache (P11-B)
- `server/arcnet_server/main.py` — all `POST` handlers use write-auth + validation helpers
- `server/arcnet_server/read_models.py` — goal excerpt in agent session/check views (P11-A)
- `server/tests/test_redteam_api.py`, `test_concurrency.py`, `test_write_auth.py` — regression suites
- `docs/32-deployment-notes.md` — write-auth + "how far from production" map (P11-C)
