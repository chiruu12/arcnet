# API coherence audit (P9-A)

Full pass over every `server/arcnet_server/main.py` route vs `docs/12-data-api.md`, tests, pagination headers, and structured `{detail, hint}` errors. **Response shapes unchanged** — doc fixes only when code and contract disagreed.

**Suite:** `uv sync --all-packages --all-groups && uv pip install pytest && .venv/bin/python -m pytest server/tests -q` — **159 passed** (baseline 149 + 10 P9-A coherence tests).

**Honesty pins (unchanged):** readiness ~64% (cap <=65, P8 remeasure in [`20`](20-honest-progress.md)); Griffin = MAD runtime (TabFM = Phase 7 stub); SigNoz MCP = PARTIAL.

---

## Audit table (33 routes)

| Endpoint | docs/12 ok | tests | errors structured | notes |
|---|---|---|---|---|
| `GET /health` | yes (P9-A row) | `test_api_coherence::test_health` | n/a | Liveness only |
| `POST /api/agents` | yes (P9-A row) | `test_api_coherence::test_write_ingest_roundtrip`, `test_hq_agent`, `test_wave_b`, `test_phase4_live_ops` | n/a | Write-secret in `test_wave_a` |
| `POST /api/sessions` | yes (P9-A row) | `test_api_coherence::test_write_ingest_roundtrip`, `test_hq_agent`, `test_phase4_live_ops` | n/a | Returns human session row |
| `POST /api/threats` | yes (P9-A row) | `test_api_coherence::test_write_ingest_roundtrip`, `test_unplug_verdict_metadata` | n/a | Publishes SSE `threat` |
| `POST /api/sources` | yes (P9-A row) | `test_api_coherence::test_write_ingest_roundtrip`, `test_unplug_verdict_metadata` | n/a | — |
| `POST /api/signal` | yes | `test_api_coherence::test_write_ingest_roundtrip`, `test_wave_a`, `test_unplug_verdict_metadata` | n/a | Write-secret in `test_wave_a` |
| `GET /api/fleet` | yes | `test_read_models`, `test_product_rework_api`, `test_agent_twins_p8b` | n/a | — |
| `GET /api/sessions/{id}` | yes | `test_read_models`, `test_product_rework_api`, `test_agent_twins_p8b` (404) | yes | `_require_session` → `api_error` |
| `GET /api/sessions` | yes | `test_product_rework_api`, `test_read_models`, `test_wave_a`, `test_phase4_live_ops` | n/a | Pagination headers tested |
| `GET /api/agents/{id}/models` | yes | `test_product_rework_api` (404) | yes | — |
| `GET /api/agents/{id}/model-intel` | yes | `test_model_intelligence`, `test_api_coherence::test_model_intel_404_structured` | yes (P9-A fix) | Was bare `HTTPException(404)` → `api_error` |
| `GET /api/agents/{id}/versions/timeline` | yes | `test_hq_agent`, `test_wave_a` | n/a | Returns empty versions for unknown agent (by design) |
| `GET /api/agents/{id}/versions` | yes | `test_hq_agent` | n/a | Pagination headers in `test_hq_agent` |
| `POST /api/agents/{id}/versions` | yes | `test_hq_agent`, `test_wave_a` | n/a | Session pin + 400 paths covered |
| `POST /api/agents/{id}/apply-model` | yes | `test_wave_b`, `test_hq_agent`, `test_agent_twins_p8b` (409), `test_api_coherence::test_apply_model_agent_404_structured` | yes | 409 duplicate `version_id` |
| `GET /api/threats` | yes | `test_read_models`, `test_api_coherence::test_list_pagination_headers` | n/a | Pagination headers (P9-A) |
| `GET /api/sources` | yes | `test_read_models`, `test_api_coherence::test_list_pagination_headers` | n/a | Pagination headers (P9-A) |
| `GET /api/signals` | yes | `test_product_rework_api`, `test_read_models`, `test_phase4_live_ops` | n/a | Pagination headers tested |
| `GET /api/replays` | yes | `test_read_models`, `test_api_coherence::test_list_pagination_headers` | n/a | Pagination headers (P9-A) |
| `POST /api/replay` | yes | `test_read_models` (400/404 validation) | partial | Happy path needs `OPENAI_API_KEY` + AgentOS — **DEFER to driver session** |
| `GET /api/agent-view/replay/{id}` | yes (P9-A row) | `test_api_coherence::test_replay_agent_view_route`, `test_read_models` (404) | yes | Separate route from `{view}/{id}` |
| `GET /api/agent-view/{view}/{id}` | yes | `test_agent_twins_p8b`, `test_read_models`, `test_robustness_pass`, `test_product_rework_api`, `test_case_file` | yes | `infer_hint` view list matches registry |
| `GET /export/case-file/{id}` | yes | `test_case_file`, `test_api_coherence::test_export_case_file_http`, `test_read_models` (404) | yes | Zip `case-file.md` + `case-file.json` |
| `GET /signals/stream` | yes | `test_api_coherence::test_signals_stream_reconnect_contract`, `test_read_models::test_signal_attribution_matches_sse_rule` | n/a | Live SSE blocks TestClient; reconnect row set matches `GET /api/signals` |
| `GET /api/hitl` | yes | `test_hitl_api`, `test_api_coherence::test_list_pagination_headers` | n/a | Pagination headers (P9-A) |
| `POST /api/hitl` | yes | `test_hitl_api` | n/a | — |
| `POST /api/hitl/{id}` | yes | `test_hitl_api`, `test_api_coherence::test_hitl_decide_404_structured` | yes | 400 invalid decision covered |
| `POST /webhooks/signoz` | yes | `test_webhook_harden` | n/a | 401 when secret set |
| `GET /api/griffin/status` | yes | `test_wave_b`, `test_tabfm_worker_stub` | n/a | MAD honesty strings |
| `POST /api/griffin/evaluate` | yes (P9-A row) | `test_api_coherence::test_griffin_evaluate` | n/a | On-demand MAD judge |
| `GET /api/signoz/status` | yes | `test_wave_b`, `test_webhook_harden`, `test_r2_r3_surface`, `test_phase3_evidence` | n/a | Live Query Range — **DEFER to driver session** when key empty |
| `GET /api/signoz/evidence` | yes | `test_wave_b`, `test_phase3_evidence`, `test_hq_tool_error_matrix` | yes | 404 missing session |

---

## Fixed in P9-A

- `GET /api/agents/{id}/model-intel` 404 now uses `api_error` with fleet hint (was bare string `HTTPException`).
- `docs/12-data-api.md`: additive rows for `GET /health`, write ingest routes (`POST /api/agents|sessions|threats|sources`), `GET /api/agent-view/replay/{id}`, `POST /api/griffin/evaluate`.
- `docs/26-agent-consumer-guide.md`: time_machine curl jq fixed to `.data | {latest_replay_id, latest_verdict}`.
- `server/tests/test_api_coherence.py`: fills gaps (health, write roundtrip, pagination headers on threats/sources/replays/hitl, export HTTP, replay twin, model-intel/hitl/apply 404, griffin evaluate, SSE reconnect).
- `errors.infer_hint` known-views list already matches agent-view registry (verified; no code change).

---

## Flagged (>50 lines — not attempted)

| Item | Why flagged |
|---|---|
| `POST /api/replay` happy-path integration | Needs live AgentOS + API key; mock would duplicate `test_replay_service` |
| Full SSE live firehose soak | 15s ping cadence; reconnect path covered instead |
| SigNoz Query Range live evidence with key | **DEFER to driver session** (worktree has no `.env`) |
| `POST /api/replay/corpus` (P1 contract row) | Not implemented — docs/12 marks P1 only; HQ packet owns corpus |
| AgentOS reload probe E2E | Covered in `test_phase4_live_ops` with mocks; full restart E2E is ops |

---

## docs/26 curl cross-check

| Curl block | Route real? | Fields match? |
|---|---|---|
| fleet_health/all | yes | `data.agents`, `data.griffin_status`, `links.threats` |
| sessions list | yes | `session_id`, `status`, `has_transcript` |
| case_files + threats | yes | `data.root_cause`, `data.export.zip`, `links.case_file` |
| export zip | yes | `application/zip` |
| models + hq_agent | yes | models array; proposals/versions/apply_endpoint |
| apply-model | yes | `confirm`, `agentos_reload_required`, `agentos_probe` |
| versions/timeline + check + griffin + time_machine | yes (time_machine jq fixed) | `.data` paths |
| replay POST + replay twin | yes | verdict fields; `REPLAY_ID` from prior run |
| structured 404/409 examples | yes | `{detail, hint}` |
