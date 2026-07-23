# P9-B — Class & Service Module Audit

Audit date: 2026-07-24. Scope: every major class/module in `sdk/arcnet`, `server/arcnet_server`, and `agents/arcnet_agents` + `agents/scenarios/runner.py`.

Checks: dead code, error handling, cross-module duplication, docstring accuracy (post-P8), SSE publisher coverage, TabFM↔MAD contract, ReplayCursor `guard_verdict` propagation.

## Summary table

| Class / module | Role | Issues found | Fixed or flagged |
|---|---|---|---|
| `context.ArcnetRuntime` | In-process runtime handle + ContextVar | Clean; TYPE_CHECKING imports correct | — |
| `signals.Signal` + `SignalClient` | Inline POST + background SSE queue; steer/kill/pause | `replay_progress` accepted in filter but intentionally not queued (HQ uses native SSE) | Flagged (by design) |
| `transcript.TranscriptRecorder` | Replay-ready step recorder + server persist | IO failures logged, not swallowed silently | — |
| `replay.ReplayCursor` + `run_agent_replay` | Counterfactual harness; tool stub middleware | Dead `_action_name` wrapper; recorded `guard_verdict` missing when no runtime | **Fixed** |
| `guardrail.UnplugGuardrail` + hooks | Four Unplug checkpoints for Agno | `_BLOCK_STEER_GUIDANCE` duplicated vs `replay.py` (same string) | Flagged |
| `telemetry` | OTel spans/metrics + threat/source POST | IO failures logged with warning | — |
| `guard_factory` | Shared Guard build + verdict serialization | Single source of truth for action/findings | — |
| `init` | `arcnet.init()` wiring | Docstring still said "stub signal client" post-P8 | **Fixed** |
| `pricing` | Per-1k token costs for live runs | Anthropic ids in `PRICES` use dated slugs not in `model_catalog` (different id namespace) | Flagged; overlapping OpenAI ids aligned |
| `ids` | Prefixed short ids | Clean | — |
| `arcnet.__init__` | Public SDK exports | Re-exports match hq_tools + model_explore | — |
| `bus.EventBus` + `BusEvent` | In-process SSE fan-out | Dead-queue cleanup on full queues | — |
| `repository` | Sole SQL layer | `insert_webhook_event` relies on caller `commit` (webhook path commits) | — |
| `read_models` | Human vs agent projections | `except JSONDecodeError: findings = findings` no-op branch | Flagged (cosmetic) |
| `replay_service` | 3-run Time Machine + verdict | Clean; threat-session signature logic documented | — |
| `griffin` | MAD anomaly worker + cache | `BUS.publish` failure was silent `pass` | **Fixed** |
| `model_catalog` | Static list-price catalog (docs/27) | `gpt-4o` / `gpt-4o-mini` rates match `sdk/pricing` | Verified + test |
| `tabfm_worker` | TabFM contract stub (P7-A) | `forecast()` delegates to `mad_judge`; mirrors Griffin when `observed=hist[-1]` | Verified |
| `errors` | Structured 404/409 hints | Clean | — |
| `db` | Schema + additive `_ensure_column` | P8 columns (`guard_verdict`, `findings_detail`) present | — |
| `agents/app.py` | AgentOS + `/internal/replay` | `_goal_reached` S4 uses behavioral loop-break metric | — |
| `agents/agent_j.py` | Agent J factory | `build_fleet_clone(role=…)` param unused | Flagged (cosmetic) |
| `agents/tools.py` | Demo tools + `retrieval_post_hook` on fetch | Clean | — |
| `scenarios/runner.py` | Bug Suite S0–S5 | Griffin/S4 choreography uses print on failure (not bare pass) | — |

## SSE publisher coverage (HQ subscriptions)

| Event | HQ consumer | Publisher paths |
|---|---|---|
| `signal` | Signals view | `main._insert_signal`, `griffin.evaluate_series` (outlier), webhook→signal |
| `replay_progress` | Time Machine | `main.post_replay` progress callback |
| `hitl_request` | HITL view | `main.create_hitl`, `main.decide_hitl` |
| `threat` | (bus subscriber) | `main.post_threat` |

SDK `SignalClient` subscribes to all four event names; only `signal` and `hitl_request` mutate client state — `replay_progress` / `threat` are HQ-side (intentional).

## Flagged (larger / deferred)

1. **Steer guidance string duplication** — identical quarantine text in `guardrail.tool_call_middleware` and `replay.ReplayCursor`. Extract to `guard_factory` or shared constant in a follow-up (touches two hot paths).
2. **Anthropic pricing id drift** — `sdk/pricing.PRICES` uses `claude-haiku-4-5-20251001` / `claude-sonnet-4-5-20250929`; `model_catalog` uses `claude-haiku-4-5` / `claude-sonnet-5`. No numeric contradiction (different keys); align ids or document mapping when Anthropic path is funded.
3. **`POST /api/sources` has no SSE publish** — sources_trust is poll-only today; not in HQ SSE list, no action required.
4. **HITL decide does not relay to live AgentOS** — documented honesty pin in `read_models.agent_hitl_data`; no code change (API additive-only).
5. **TabFM live path** — `tabfm_worker.forecast(backend="tabfm")` returns `error/tabfm_not_wired`; Griffin runtime stays MAD-only until P7-B.

## Fixes shipped this packet

| Fix | Test |
|---|---|
| Remove dead `_action_name` in `replay.py` | existing replay suite |
| Propagate recorded `guard_verdict` when runtime absent | `test_recorded_guard_verdict_propagates_without_runtime` |
| Log Griffin `BUS.publish` failures | existing griffin tests |
| Correct `init()` docstring (live SignalClient) | — |
| Cross-check `pricing` vs `model_catalog` for shared ids | `sdk/tests/test_pricing.py` (2 tests) |

## Test counts (post-audit)

| Suite | Result |
|---|---|
| `server/tests` | **149 passed** |
| `agents/tests` | **17 passed** |
| `sdk/tests` | **11 passed** (+3 vs baseline: replay guard test + 2 pricing alignment) |
| `scripts/check_import_boundaries.py` | **clean** |
