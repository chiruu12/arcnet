# ArcNet — Unplug coverage matrix (WS8 / P5-A, hardened P8-D)

**Date:** 2026-07-24  
**Packet:** P5-A ([`docs/22-next-agent-packets.md`](../22-next-agent-packets.md)) · P8-D verdict metadata  
**Scope:** In-process Unplug at four Agno checkpoints — no guard threshold changes in this packet.

## Summary

| Metric | Count |
|---|---:|
| **Total rows** | 128 |
| COVERED | 99 |
| N/A (checkpoint not on tool path) | 29 |
| DEFER (explicit gap) | 0 |

**P8-D hardening:** shared guard config in `sdk/arcnet/guard_factory.py` (`build_guard` / `arcnet_guard_config`); verdict metadata (`rule`, `pattern_class`, `risk_score`, `findings`) threaded through transcript steps, `POST /api/threats`, `POST /api/sources`, steer `POST /api/signal`, and case-file export (`root_cause.findings`, timeline `guard.rule`). Proof: `sdk/tests/test_guard_factory.py`, `server/tests/test_unplug_verdict_metadata.py`, `agents/tests/test_guard_scenarios.py::test_s1_tool_call_blocks_tainted_send_email`.

**In-scope agents:** Agent J, fleet clones L & O, HQ Agent.  
**Out of scope (explicit DEFER below):** model-explore MCP agent, SigNoz MCP stdio, server-only ingest paths.

### Live scenario regression (S1 / S2 / S5)

| Scenario | CI in this worktree | Driver session (live) |
|---|---|---|
| S1 Edgar | `agents/tests/test_s1_fixture.py` (fixture + taint block contract) | `PYTHONPATH=sdk:agents uv run python agents/scenarios/runner.py --scenario S1` + `OPENAI_API_KEY` |
| S2 Neuralyzer | `agents/tests/test_guard_scenarios.py::test_s2_output_post_hook_redacts_ssn` | `runner.py --scenario S2` + key + server |
| S5 Frank | `agents/tests/test_guard_scenarios.py::test_s5_*` | `runner.py --scenario S5` + key + server |

This worktree has **no `.env` / API key** — live scenario re-runs are **DEFER** to the operator driver session. Unit stubs above are CI-equivalent for checkpoint behavior.

**Driver close-out (2026-07-24, funded key):** live re-runs **PASS** — S1 `s_352fb834` (exfil blocked + steer), S2 `s_2458eb25` (redact; threat row carries `findings_detail`/`pattern_class`/`guard_verdict` end-to-end), S5 `s_ac9f30b3` (jailbreak block, 7 rules recorded). Hero re-verify G4 **PASS** (3/3 stable both heroes, [`../_phase4_g4.json`](../_phase4_g4.json)). The live-rerun DEFER is closed.

### Checkpoint → unplug call (reference)

| Checkpoint | Agno surface | unplug call | verdict persisted |
|---|---|---|---|
| `input` | `pre_hooks` → `UnplugGuardrail` | `guard.scan(text, USER)` | `threats` + `sources` rows via `sdk/arcnet/telemetry.py` |
| `retrieved` | `fetch_url` `post_hook` + middleware fallback | `scan(RETRIEVED)` + `wrap_for_context` + `notify_taint_source` | transcript `guard` + `sources` row |
| `tool_call` | `tool_hooks` middleware | `check_tool_call(name, args, taint_sources=…)` | transcript `guard` + `threats` + steer `signals.guard_verdict` |
| `output` | `post_hooks` | `scan_output(text)` → redact | `threats` row (`findings_detail`) |

## Coverage table

| Agent | Tool | Checkpoint | Status | Proof |
|---|---|---|---|---|
| agent_j | fetch_url | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) |
| agent_j | fetch_url | retrieved | COVERED | `sdk/arcnet/guardrail.py::retrieval_post_hook` · `agents/tests/test_s1_fixture.py` · `test_guard_scenarios.py::test_retrieved_post_hook_taints_fetch_output` |
| agent_j | fetch_url | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` |
| agent_j | fetch_url | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_j | lookup_customer | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) |
| agent_j | lookup_customer | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_j | lookup_customer | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` |
| agent_j | lookup_customer | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_j | get_customer_profile | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) |
| agent_j | get_customer_profile | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_j | get_customer_profile | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` |
| agent_j | get_customer_profile | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_j | send_email | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) |
| agent_j | send_email | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_j | send_email | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` |
| agent_j | send_email | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_j | run_query | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) |
| agent_j | run_query | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_j | run_query | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` |
| agent_j | run_query | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_j | paginate_records | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) |
| agent_j | paginate_records | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_j | paginate_records | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` |
| agent_j | paginate_records | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_l | fetch_url | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_l | fetch_url | retrieved | COVERED | `sdk/arcnet/guardrail.py::retrieval_post_hook` · `agents/tests/test_s1_fixture.py` · `test_guard_scenarios.py::test_retrieved_post_hook_taints_fetch_output` |
| agent_l | fetch_url | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_l | fetch_url | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_l | lookup_customer | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_l | lookup_customer | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_l | lookup_customer | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_l | lookup_customer | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_l | get_customer_profile | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_l | get_customer_profile | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_l | get_customer_profile | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_l | get_customer_profile | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_l | send_email | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_l | send_email | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_l | send_email | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_l | send_email | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_l | run_query | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_l | run_query | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_l | run_query | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_l | run_query | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_l | paginate_records | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_l | paginate_records | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_l | paginate_records | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_l | paginate_records | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_o | fetch_url | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_o | fetch_url | retrieved | COVERED | `sdk/arcnet/guardrail.py::retrieval_post_hook` · `agents/tests/test_s1_fixture.py` · `test_guard_scenarios.py::test_retrieved_post_hook_taints_fetch_output` |
| agent_o | fetch_url | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_o | fetch_url | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_o | lookup_customer | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_o | lookup_customer | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_o | lookup_customer | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_o | lookup_customer | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_o | get_customer_profile | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_o | get_customer_profile | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_o | get_customer_profile | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_o | get_customer_profile | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_o | send_email | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_o | send_email | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_o | send_email | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_o | send_email | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_o | run_query | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_o | run_query | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_o | run_query | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_o | run_query | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| agent_o | paginate_records | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/arcnet_agents/agent_j.py::build_fleet_clone` shares `build_guard_hooks()` |
| agent_o | paginate_records | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| agent_o | paginate_records | tool_call | COVERED | `sdk/arcnet/guardrail.py::tool_call_middleware` · S1 `send_email` block / S3 `run_query` in `test_guard_scenarios.py` · clone wiring |
| agent_o | paginate_records | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) |
| hq_agent | signoz_status | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | signoz_status | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | signoz_status | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | signoz_status | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | signoz_evidence | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | signoz_evidence | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | signoz_evidence | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | signoz_evidence | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | fleet_overview | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | fleet_overview | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | fleet_overview | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | fleet_overview | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | agent_signals | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | agent_signals | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | agent_signals | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | agent_signals | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | session_check | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | session_check | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | session_check | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | session_check | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | case_file_view | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | case_file_view | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | case_file_view | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | case_file_view | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | replay_compare | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | replay_compare | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | replay_compare | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | replay_compare | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | griffin_anomalies | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | griffin_anomalies | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | griffin_anomalies | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | griffin_anomalies | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | list_agent_models | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | list_agent_models | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | list_agent_models | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | list_agent_models | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | recommend_models | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | recommend_models | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | recommend_models | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | recommend_models | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | agent_version_timeline | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | agent_version_timeline | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | agent_version_timeline | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | agent_version_timeline | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | register_agent_version | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | register_agent_version | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | register_agent_version | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | register_agent_version | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | propose_model_change | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | propose_model_change | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | propose_model_change | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | propose_model_change | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |
| hq_agent | list_model_proposals | input | COVERED | `sdk/arcnet/guardrail.py::UnplugGuardrail.check` · `agents/tests/test_guard_scenarios.py` (S5 stub) · `agents/hq_agent/agent.py::build_hq_agent` · `arcnet.init` + `build_guard_hooks()` |
| hq_agent | list_model_proposals | retrieved | N/A | No retrieval tool in agent toolkit — checkpoint not on code path |
| hq_agent | list_model_proposals | tool_call | COVERED | `tool_call_middleware` on every HQ `@tool` · `agents/tests/test_hq_agent.py::test_build_hq_agent_has_tools_and_guards` |
| hq_agent | list_model_proposals | output | COVERED | `sdk/arcnet/guardrail.py::output_post_hook` · `agents/tests/test_guard_scenarios.py` (S2 stub) · bounded excerpts `sdk/arcnet/hq_tools.py` |

## Explicit DEFER (out of matrix — not silent holes)

| Surface | Reason |
|---|---|
| Model explore Agno agent / `skills/arcnet-model-explore` MCP | Out of P5-A product-agent scope; exploration-only |
| SigNoz MCP stdio | Documented PARTIAL; HQ Agent prefers HTTP `signoz_evidence` |
| `POST /api/signal` reason/guidance | Server ingest — unplug scan of free-text **DEFER** (driver session); steer rows from runtime carry `guard_verdict` JSON when emitted by `tool_call_middleware` |
| Live S1/S2/S5 `runner.py` E2E | Requires `OPENAI_API_KEY` + server — driver session |
| Agent K (P2) | Not built; L & O satisfy fleet background |

## Verification commands

```bash
PYTHONPATH=sdk:server:. uv run python -m unittest discover -s agents/tests
uv run python scripts/check_import_boundaries.py
uv run pytest server/tests
PYTHONPATH=sdk:agents uv run pytest agents/tests
uv run python -m unittest discover -s sdk/tests
cd hq && pnpm test && pnpm build
```
