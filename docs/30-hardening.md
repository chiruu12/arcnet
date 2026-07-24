# API Hardening — Adversarial Red-Team (P11-A)

Offline adversarial suite: `server/tests/test_redteam_api.py`. Every attack below is asserted in CI; verdict is **safe** (already OK), **fixed** (hole patched this packet), or **deferred** (known gap, not attempted).

## 1. Malformed bodies

| Attack | Endpoints | Verdict |
|--------|-----------|---------|
| Non-JSON body (`not-json`, empty) | All `POST` JSON routes | **fixed** — `parse_json_object()` → 400 `{detail}` |
| JSON array / `null` instead of object | All `POST` JSON routes | **fixed** — 400 `body must be a JSON object` |
| Missing required fields (`agent_id`, `run_id`, signal fields) | `/api/agents`, `/api/sessions`, `/api/signal`, `/api/hitl` | **fixed** — 400 `missing required field(s): …` |
| Wrong types (int `agent_id`, array `reason`) | Write routes | **safe** — SQLite accepts or route returns 4xx; no 500 |
| Deeply nested JSON (depth 80) | `/api/sessions` transcript | **safe** — parses; bounded by transcript byte cap on write |

Webhook (`/webhooks/signoz`) was already hardened in Wave A — **safe** (regression guarded).

## 2. Path / param injection

| Attack | Verdict |
|--------|---------|
| `../`, URL-encoded traversal in `session_id` / `agent_id` / `view` / `hitl_id` | **safe** — literal SQLite lookup → 404; no filesystem read |
| SQL meta (`' OR 1=1--`, `;DROP TABLE`) in path or query | **safe** — parametrized `?` placeholders throughout `repository.py` |
| 10 KB-long ids | **safe** — 404; no OOM |
| Unicode / RTL override chars | **safe** — 404 or empty result |
| NUL bytes in path | **safe** — client URL layer rejects; server never reached |
| Case-file export with traversal id | **safe** — zip built from DB row only; 404 when missing |

## 3. Pagination abuse

| Attack | Routes | Verdict |
|--------|--------|---------|
| `limit` / `offset` negative, zero, `10**9`, non-numeric, float | All paginated `GET` lists | **safe** — FastAPI `Query(ge=, le=)` → 422 |
| Duplicate query params (`limit=5&limit=3`) | `/api/sessions` | **safe** — framework picks last value |

## 4. Oversized payloads

| Field | Cap | Verdict |
|-------|-----|---------|
| `transcript` (serialized JSON) | 1 MiB | **fixed** — 422 on write |
| `goal`, `evidence`, `reason`, `guidance` | 16 KiB chars | **fixed** — 422 on write |
| `hitl.payload`, `sources.findings_detail` | 64 KiB JSON | **fixed** — 422 on write |
| Agent-view `goal` echo | 200 chars excerpt | **fixed** — `agent_session_context` + `session_check_data` now excerpt |
| Case-file zip / incident envelope | excerpt caps | **safe** — already bounded (regression guarded) |
| Human `GET /api/sessions/{id}?include=transcript` | unbounded by design | **deferred** — docs/12 intentional; localhost-trust model |

5 MiB ingest attempts are rejected at the API layer; agent-view and case-file responses stay under excerpt caps.

## 5. Content-type / header abuse

| Attack | Verdict |
|--------|---------|
| Missing `Content-Type` | **safe** — `request.body()` + `json.loads` |
| Wrong charset (`iso-8859-1` on UTF-8 body) | **safe** — parses |
| Duplicate query params | **safe** |

## 6. Write-secret bypass (`ARCNET_WRITE_SECRET`)

| Attack | Routes | Verdict |
|--------|--------|---------|
| No header / wrong secret / empty header | `POST /api/agents`, `/api/sessions`, `/api/threats`, `/api/sources`, `/api/signal`, `/api/agents/{id}/versions` | **safe** — 401; no partial write (regression guarded) |
| Bearer vs `X-ArcNet-Write-Secret` | Same | **safe** |
| `POST /api/agents/{id}/apply-model` without secret | apply-model | **safe** — human-gated via `confirm: true`; not write-secret scoped (docs/12) |

## Deferred (not attempted this packet)

- **Auth on read paths** — localhost-trust by design; bind `127.0.0.1` + env secrets for deploy.
- **Request body size limit at ASGI layer** — app-level JSON caps only; reverse proxy should set `client_max_body_size`.
- **Rate limiting / slowloris** — out of scope for SQLite-primary v1.
- **Live-key paths** (AgentOS replay, SigNoz Query Range) — require env keys; offline tests mock or skip.
- **SSE stream abuse** — long-lived connection; no per-connection cap in v1.
- **Full transcript on human read API** — intentional A15 hatch; agent views stay bounded.

## Files changed

- `server/arcnet_server/validation.py` — JSON parse, required fields, size bounds
- `server/arcnet_server/main.py` — all `POST` handlers use validation helpers
- `server/arcnet_server/read_models.py` — goal excerpt in agent session/check views
- `server/tests/test_redteam_api.py` — adversarial regression suite
- `docs/30-hardening.md` — this document
