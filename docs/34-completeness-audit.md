# ArcNet completeness audit (P31 re-audit)

Evidence-based audit of shipped surface vs `docs/01-product.md` (P0/P1/P2),
`docs/03-plan.md` (phase exits G1–G5), `docs/15-product-map.md`, and
`docs/20-honest-progress.md`. Method: every claim traced to route, module, UI
view, and test; buckets are mutually exclusive.

**Date:** 2026-07-25  
**Branch:** `main` (post P21–P30)  
**Verdict:** The **P0 demo loop is shippable** (observe → defend → replay → case
file) with honest `mixed` hero verdicts. A cold clone reproduces both hero
incidents with **no API key** (`fixtures/heroes.json` + `scripts/seed_heroes.py`).
The product is **not complete** against the full v2 spec: human ship assets,
live MCP handoff, live-work dogfood, and unplug-ai input-layer gaps remain open
or explicitly deferred. Overall readiness **~64% / ≤65%** in `docs/20` is
**supported** — not inflated.

---

## 1. Test suite counts (measured this audit)

| Suite | Command | Result |
|-------|---------|--------|
| **server** | `.venv/bin/python -m pytest server/tests -q` | **233 passed** |
| **sdk** (unittest) | `PYTHONPATH=sdk:server uv run python -m unittest discover -s sdk/tests -q` | **14 passed** |
| **sdk** (pytest) | `PYTHONPATH=sdk .venv/bin/python -m pytest sdk/tests -q` | **81 passed** (incl. guard corpus + canary) |
| **agents** | `PYTHONPATH=sdk:server:. uv run python -m unittest discover -s agents/tests -q` | **18 passed** |
| **hq** | `cd hq && pnpm test` | **97 passed** |
| **import boundaries** | `uv run python scripts/check_import_boundaries.py` | **clean** |

**Note:** `unittest discover -s sdk/tests` alone finds **14** tests — the pytest corpus
(`test_guard_corpus.py`, `test_canary.py`, etc.) is not included. Use the pytest line for
the full sdk count. `server/tests/conftest.py` plus module-level `ARCNET_SERVER_URL` guards
in `sdk/tests/test_replay.py` and `agents/tests/test_guard_scenarios.py` keep suites from
writing into `data/arcnet.db`.

---

## 2. Bucket summary

| Bucket | Count | Notes |
|--------|------:|-------|
| **SHIPPED** | **47** | Code + test + UI or documented API reachable |
| **PARTIAL** | **9** | Exists; material gap named |
| **MISSING** | **2** | Planned, no implementation |
| **EXPLICIT DEFER** | **7** | Documented cut or human-only |

P0 items not **SHIPPED**: **2** (F4 SigNoz MCP live, F7 MCP handoff — see §3). All other P0
features are **SHIPPED** or **PARTIAL** with a named, non-blocking gap.

---

## 3. P0 feature matrix (demo-critical)

| ID | Feature | Bucket | Evidence | Gap (if not SHIPPED) |
|----|---------|--------|----------|----------------------|
| **F1** | Instrumented fleet (SigNoz + Agno OpenInference) | **SHIPPED** | `sdk/arcnet/init.py:29-59` OTLP + `AgnoInstrumentor`; `agents/arcnet_agents/app.py:16-41` AgentOS fleet; Phase 0 trace attrs in `docs/04` | — |
| **F2** | Trust & guard telemetry (`arcnet.guard.*`, 4 checkpoints) | **SHIPPED** | `sdk/arcnet/guardrail.py:18-80` input + retrieved; tool/output in same file; `sdk/tests/test_guard_factory.py:17-36`; `agents/tests/test_guard_scenarios.py:41-113` S1/S2/S5 stubs | — |
| **F3** | Bug Suite S0/S1/S2/S4/S5 | **SHIPPED** | `agents/scenarios/runner.py:81-651` all five scenarios + assertions; `agents/tests/test_s1_fixture.py:30-63`; CI stubs when no live key (`agents/tests/test_guard_scenarios.py:1-3` header) | Live `runner.py --scenario all` needs `OPENAI_API_KEY` (quota-gated per `docs/20`) |
| **F4** | SigNoz depth (dashboards, alerts, webhook) | **PARTIAL** | Provision: `deploy/provision/dashboard-*.json`, `alerts.json`, `setup.py:101-283`; webhook `server/arcnet_server/main.py:1089-1123`; tests `server/tests/test_webhook_harden.py:28-108`; status `main.py:1253-1259`; HQ UUID resolve `hq/src/dashboardLinks.ts` + `Dashboards.tsx:124-149` | **MCP live** = PARTIAL (`deploy/mcp/README.md:12` key-less fail; G5 deferred). **Service-account key** = manual UI step. Unresolved boards show explicit copy instead of silently opening generic shell |
| **F5** | Signals self-correct (`steer`/`kill`) | **SHIPPED** | `sdk/arcnet/signals.py:98-163` apply_steer/kill; inline `main.py:262-272`; SSE `main.py:964-979`; HQ `hq/src/views/Signals.tsx` + SSE bus | `pause` scaffold only (see P1 HITL) |
| **F6** | Fleet Health view | **SHIPPED** | `hq/src/views/FleetHealth.tsx:124-168`; API `main.py:273-277`; `[FORWARD]` badge `FleetHealth.tsx:155-156`; tests via FE + `server/tests/test_read_models.py` fleet envelope | **Latency** on cards: p50/p95 wall-clock ms from recorded session timestamps (`ended_at-started_at`, fallback `usage.latency_ms`) — **SHIPPED** P26 |
| **F7** | Agent-view + Case File + MCP handoff | **PARTIAL** | Agent-view `main.py:673-933`; Case File `main.py:953-958`; tests `server/tests/test_case_file.py:67-88`; twins `server/tests/test_agent_twins_p8b.py:97-168`; MCP hints `read_models.py:123-129` | **G5 live MCP handoff** = **EXPLICIT DEFER** (`docs/03-plan.md:91`, `docs/log.md:62`). HTTP/Query Range fallback shipped; stdio may hang |
| **F13** | Griffin core (MAD) | **SHIPPED** | Worker `server/arcnet_server/griffin.py:613-628`; evaluate `main.py:1192+`; MAD tests `server/tests/test_griffin_cold_soak.py`; HQ strip `FleetHealth.tsx:34-72` | Default runtime = **MAD**; TabFM opt-in `ARCNET_TABFM=1` (`griffin.py:143-144`) — narrate honestly |
| **F14** | Time Machine (counterfactual replay + verdict) | **SHIPPED** | Harness `sdk/arcnet/replay.py:1-30`; API `main.py:583-619`; UI `hq/src/views/TimeMachine.tsx`; verdict tests `server/tests/test_replay_service.py:42-103`; hardening `server/tests/test_replay_hardening.py`; G4 `docs/_phase4_g4.json` | Live `replay.run()` needs AgentOS `:7777` + OpenAI key |

**P0 rollup:** 7 SHIPPED · 2 PARTIAL (F4, F7). No P0 **MISSING**.

---

## 4. P1 feature matrix

| Feature | Bucket | Evidence | Gap |
|---------|--------|----------|-----|
| Native SigNoz seasonal anomaly alert | **SHIPPED** (artifact) | `deploy/provision/alert-seasonal-anomaly.json:3-13` `never_demo_live`; provision `setup.py:282-283` | Cannot fire on camera (≥5m windows) — pairing story only |
| Griffin breadth (auto-discovery, top-N) | **SHIPPED** | Auto-discovery from seed/SQLite proxy `griffin.py` `discover_series_ids` + `run_evaluation_cycle`; eval cap `ARCNET_GRIFFIN_EVAL_CAP` (default 12); top-N `ARCNET_GRIFFIN_TOP_N` (default 3) in `cache_snapshot.top_series`; `DEFAULT_SERIES_PRIORITIES` fallback ordering | — |
| Sources & Trust view | **SHIPPED** | `hq/src/views/SourcesTrust.tsx`; `GET /api/sources` `main.py:521-539`; ledger schema `docs/12` | Poll-only — **sources SSE** = **EXPLICIT DEFER** (`docs/29-class-audit.md:49`, by design) |
| HITL `pause` beat | **SHIPPED** | UI `hq/src/views/Hitl.tsx`; API `main.py:1090-1107`; relay `hitl_relay.py` (reject → kill on signal bus + AgentOS `/internal/hitl-decide`; approve = acknowledgement only); honesty `hq/src/hitlUtils.ts:26-27`; tests `server/tests/test_hitl_api.py` | `pause` signal scaffold only — approve does **not** resume a live Agno run |
| Prompt-swap replay | **SHIPPED** | API `candidate_prompt` `main.py:596-627`; HQ model/prompt axis `TimeMachine.tsx:361-584`; tests `server/tests/test_replay_hardening.py` | Live `replay.run()` still needs AgentOS + model key |
| Live-work agent (dogfood fleet) | **PARTIAL** | Agent J + L/O `agents/arcnet_agents/app.py:30-36`; seed background sessions `scripts/seed_demo.py:27-131` | Agents run **scenario choreography** + seeded background rows — not continuous genuine production tasks |
| Time Machine corpus scorecard | **SHIPPED** | `POST /api/replay/corpus` `main.py`; `corpus_service.py` stored+live modes; HQ `TimeMachine.tsx` stored scorecard strip; tests `server/tests/test_corpus_and_latency.py` | Live mode needs AgentOS + model key; stored mode works offline on seeded replays |
| Context inspector UI | **SHIPPED** | HQ `hq/src/views/ContextInspector.tsx` + `contextInspector.ts` ingest timeline; composes `/api/sources` + `/api/agent-view/threats/{id}`; hash route `#context_inspector?session=…`; tests `hq/src/contextInspector.test.ts` | No dedicated server route — agent mode builds envelope client-side (`ContextInspector.tsx:67`) |
| F9 canaries | **SHIPPED** | `guard.add_canary` via `plant_canary_prompt` in `agents/arcnet_agents/agent_j.py` + `agents/hq_agent/agent.py`; detection at `output` / `tool_call` through existing `scan_output` path (`sdk/arcnet/guardrail.py`); tests `sdk/tests/test_canary.py` | Per-session token never exported — redacted from transcript args + threat payloads |

---

## 5. Phase exits & gates

| Gate / exit | Bucket | Evidence |
|-------------|--------|----------|
| G1 replay + steer spike | **SHIPPED** | `docs/log.md`; `sdk/tests/test_replay.py:49-191` recorded steer/kill |
| G2 TabFM spike | **SHIPPED** | `docs/_phase2_g2.json`; decision MAD primary |
| G3 replay tripwire | **SHIPPED** | Phase 3 exit `docs/03-plan.md:73-75` |
| G4 hero replay stability | **SHIPPED** | `docs/_phase4_g4.json`; `server/tests/test_replay_service.py:65-103` threat stability |
| G5 MCP handoff (live) | **EXPLICIT DEFER** | `docs/03-plan.md:91`; `deploy/mcp/README.md:12`; Case File HTTP fallback `read_models.py:123-129` |
| Phase 5 UI + Case File | **SHIPPED** | Ten HQ views + `home` + `hitl` + `hq_agent` + `context_inspector` in `hq/src/App.tsx:17-21`; hash routes `hq/src/hash.ts:12-27` |
| Phase 6 ship (video, screenshots, submit) | **EXPLICIT DEFER** | `docs/03-plan.md:99-103`; README screenshot slots empty (`README.md:159` — capture deferred) |
| P7-B TabFM ship | **PARTIAL** | Code `griffin.py:53-315`; tests `server/tests/test_tabfm_griffin.py:57-172`; live verify `docs/_phase7_p7b_live.json` | **Default off** — `ARCNET_TABFM=1` required; HQ still labels MAD unless worker live |

---

## 6. HQ views (built surface)

| View | Bucket | Route / API | Test |
|------|--------|-------------|------|
| **home** | **SHIPPED** | `hq/src/views/Home.tsx:7-25`; twin `test_agent_twins_p8b.py:97-103` | P8 — **not** in `docs/15` §4.1 inventory |
| **fleet_health** | **SHIPPED** | `FleetHealth.tsx`; `/api/fleet` | FE + read_models |
| **signals** | **SHIPPED** | `Signals.tsx:185-207` renders `guidance`; SSE | `apiResilience.test.ts` |
| **hitl** | **SHIPPED** | `Hitl.tsx` + `/api/hitl`; relay `hitl_relay.py` + `relay` field on decide | Approve = ack only; `pause` scaffold |
| **sources_trust** | **SHIPPED** | `SourcesTrust.tsx`; `/api/sources` | — |
| **context_inspector** | **SHIPPED** | `ContextInspector.tsx`; sources + threats timeline | Client-composed agent twin; no server route |
| **time_machine** | **SHIPPED** | `TimeMachine.tsx:550` `hand_to(claude_code)`; model **or** prompt swap | `test_replay_*` |
| **case_files** | **SHIPPED** | `CaseFiles.tsx`; export `main.py:953-958`; download error seam `CaseFiles.tsx:324` | `test_case_file.py:88` |
| **dashboards** | **SHIPPED** | `Dashboards.tsx` + `dashboardLinks.ts`; UUID deep-link when env/status set; unresolved boards labeled | No embedded charts |
| **hq_agent** | **SHIPPED** | `HqAgent.tsx`; propose/apply/pin APIs | `server/tests/test_hq_agent.py` | P8 — thin in `docs/15` |

**Hash routing:** `hq/src/hash.ts:12-27`, `App.tsx:31-42` — **SHIPPED**.

---

## 7. Known deferrals (confirmed)

| Deferral | Still accurate? | Evidence |
|----------|-----------------|----------|
| P6-C corpus scorecard | **No** | `POST /api/replay/corpus` shipped P26 — stored (offline) + live (bounded) |
| G5 live MCP handoff | **Yes** | `deploy/mcp/README.md:12`; hints prefer HTTP `read_models.py:123-129` |
| README screenshots | **Yes** | `README.md:159` — slots reserved, capture human |
| Context-inspector UI | **No** | `hq/src/views/ContextInspector.tsx` shipped P30 |
| HITL live relay | **No** | `hitl_relay.py` + `main.py:1105-1107`; bounded 2s timeout; `ARCNET_AGENTOS_URL=""` disables HTTP hop |
| Sources SSE | **Yes** | Only `/signals/stream` SSE `main.py:964`; `docs/29-class-audit.md:49` |
| Track H (video/submission/Slack) | **Yes** | `docs/22-next-agent-packets.md:218` H-1 TODO |
| S3 Serleena / F10 judge / F11 adapter | **Yes** | P2 cut; no runner for S3 |
| unplug-ai input-layer gaps (9) | **Yes** | `docs/33-guard-coverage.md` §Known gaps — upstream PyPI package, not modified in this repo |

---

## 8. Built but under-documented

| Surface | Evidence | Doc gap |
|---------|----------|---------|
| `home` landing + loop stats | `hq/src/views/Home.tsx:7-25` | Missing from `docs/15` §4.1 |
| `context_inspector` ingest timeline | `hq/src/views/ContextInspector.tsx`; `contextInspector.ts` | New P30 — add to `docs/15` §4.1 |
| `hq_agent` maintenance strip | `hq/src/views/HqAgent.tsx`; `GET /api/agents/{id}/model-intel` `main.py:334-346` | `docs/18-hq-agent.md` aspirational vs shipped subset |
| Hero fixture cold-clone | `fixtures/heroes.json` + `scripts/seed_heroes.py` in `run-demo.sh` | 17 stored replay verdicts per hero; no OpenAI key |
| Write-auth (`ARCNET_WRITE_SECRET`) | `docs/30-hardening.md` P11-C; `server/tests/test_write_auth.py` | Not in `docs/01` feature tiers |
| Guard corpus P14 (45 payloads) | `sdk/tests/test_guard_corpus.py`; `docs/33-guard-coverage.md` 28/40 (70.0%) | Not in product map §4 |
| HQ resilience P13 + P27 | `hq/src/apiResilience.ts`; per-view retry (`viewRetry.ts`); SSE `StreamStatus`; envelope validation; 97 FE tests | Post-P8 hardening |

---

## 9. Docs overstate (evidence)

| Claim | Reality | Severity |
|-------|---------|----------|
| `docs/15` fleet cards "no latency" | p50/p95 wall-clock ms + `latency_source_24h` on cards `FleetHealth.tsx:192-213` | Low — map stale |
| `docs/20` test counts | **233 / 81 / 97** measured above (was 219/63/60) | Low — tracking drift |
| `docs/22` P7-B "**DONE**" TabFM | Shipped **opt-in**; default MAD `griffin.py:143-144`; HQ honesty string `FleetHealth.tsx:72` | Medium — risk if demo claims TabFM without `ARCNET_TABFM=1` |
| `docs/15` `POST /api/replay/corpus` GAP | Endpoint + HQ scorecard strip shipped P26 | Low — map stale |
| `docs/15` HITL "no AgentOS relay" | `hitl_relay.py` ships reject → kill relay | Low — map stale |
| "Every panel has agent-view twin" (`docs/01`) | Largely true post-P8; `context_inspector` twin is HQ-composed | Low — note composition |

**Honesty scores (`docs/20`):** Overall **~64%** is **defensible**. Area **10
Unplug 80** is supported (`docs/plans/unplug-coverage-matrix.md` 128 rows +
`docs/33` corpus 28/40 at 70.0%). Area **2 HQ 74** is fair (10 views, hash routes, 97 FE
tests). Area **11 Tests 68** is fair given 233 server tests.
**Demo readiness 58%** is honest (quota-blocked live reruns, no capture assets).
**Do not bump overall past 65%** without live S1/S2/S5 rerun + capture — agree
with `docs/20` cap.

---

## 10. Import boundary

**SHIPPED** — `scripts/check_import_boundaries.py` exit 0: `sdk/`, `server/`,
`hq/` never import `agents/` or `scripts/`.

---

## 11. Ranked gap list

Ordered by **user-visible impact × effort to close** (highest first).

| Rank | Gap | Close with |
|------|-----|------------|
| 1 | **Hackathon capture** (screenshots, video, submission) — blocks external judgment | Human: run `scripts/run-demo.sh`, capture per `docs/plans/capture-checklist.md`, fill README slots |
| 2 | **Live hero replay re-verify** (OpenAI quota) — recorded G4 may be stale | Top up key; rerun `scripts/phase4_g4_check.py`; refresh `docs/_phase4_g4.json` |
| 3 | **G5 / SigNoz MCP live handoff** — Case File beat relies on HTTP fallback | Provision `SIGNOZ_API_KEY`; debug stdio hang or document HTTP-only path in demo script |
| 4 | ~~**HITL pause does not stop AgentOS**~~ | **SHIPPED** P21 — reject → kill on signal bus + AgentOS; approve = ack only (`hitl_relay.py`) |
| 5 | ~~**Dashboard UUID deep-links**~~ | **SHIPPED** P22 — `dashboardLinks.ts`; unresolved boards labeled, not silently generic |
| 6 | ~~**Time Machine corpus scorecard**~~ | **SHIPPED** P26 — `POST /api/replay/corpus` + HQ stored scorecard |
| 7 | ~~**Prompt-swap replay UI**~~ | **SHIPPED** P22 — model/prompt axis in `TimeMachine.tsx` |
| 8 | ~~**Fleet Health latency dimension**~~ | **SHIPPED** P26 — p50/p95 wall-clock ms on fleet cards |
| 9 | ~~**Griffin auto-discovery / top-N**~~ | **SHIPPED** P29 — discovery + eval cap + top-N status |
| 10 | ~~**F9 canaries**~~ | **SHIPPED** P28 — `plant_canary_prompt` + leak detection + `sdk/tests/test_canary.py` |
| 11 | ~~**Context inspector**~~ | **SHIPPED** P30 — `ContextInspector.tsx` ingest timeline (client-composed twin) |
| 12 | **Live-work dogfood agent** — fleet is scenario + seed theater | Long-running AgentOS task loop outside scenario runner |
| 13 | ~~**Doc hygiene**~~ | **SHIPPED** P31 — product map + audit aligned to P21–P30 |
| 14 | ~~**README verification commands**~~ | **SHIPPED** P20 — pytest line documented; counts refreshed P31 |
| 15 | **unplug-ai input-layer gaps (9)** | Upstream `unplug-ai` PyPI package — see `docs/33` §Known gaps; ArcNet does not modify it |

---

## 12. Final verdict

| Question | Answer |
|----------|--------|
| Is the product **complete** vs the v2 spec? | **No** — human ship assets, live MCP handoff, live-work dogfood, and unplug-ai input-layer gaps remain open or deferred. |
| Is the **P0 demo loop** complete? | **Yes, with named caveats** — heroes (cold-clone reproducible), Time Machine, guard, signals, Case File, and HQ views are real; MCP live and capture are the weak beats. |
| Biggest honest risk on camera? | Operator must **select hero sessions** (defaults ≠ G4 rows); narrate **MAD not TabFM** unless `ARCNET_TABFM=1`; do not claim live MCP without key; HITL approve is ack-only. |
| Counts | **47 SHIPPED · 9 PARTIAL · 2 MISSING · 7 EXPLICIT DEFER** |

---

## Related

- Intent: `docs/01-product.md`, `docs/03-plan.md`
- Inventory: `docs/15-product-map.md` (partially stale — see §9)
- Honesty pin: `docs/20-honest-progress.md`
- Packet tracking: `docs/22-next-agent-packets.md`
- Hardening style reference: `docs/30-hardening.md`
