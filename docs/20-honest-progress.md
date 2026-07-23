# ArcNet — Honest progress measurement (post P8 remeasure)

**Date:** 2026-07-24 (P8 remeasure; 07-23 PM baseline ~62%, AM ~57%)  
**Branch:** `main` @ Phases 5–6 + P7-A + P8 wave merged (P8-A graph / P8-B twins / P8-C model-intel / P8-D verdict metadata)  
**Rule:** overall product readiness **≤65%** until the next exits pass (live S1/S2/S5 rerun, P7-B TabFM ship, demo capture). No 74/80/95 theater.

Companion: [`19-path-to-95.md`](19-path-to-95.md) (plan), [`plans/path-to-95-acceptance.md`](plans/path-to-95-acceptance.md) (acceptance scripts), [`21-next-phases-plan.md`](21-next-phases-plan.md) (post–Wave B phase bundles + TabFM research), [`23-product-overview.md`](23-product-overview.md) (product overview).

---

## 1. Verdict

| Slice | Honest % | Evidence basis |
|---|---:|---|
| Shipped surface (APIs/UI/tools exist) | **72** | + P8: agent-view twin for every HQ view w/ cross-links, `model-intel` endpoint + catalog, home landing, frontend map — all test-covered |
| Reliability (timeouts, flakes, reload honesty) | **60** | + shell recover helper w/ tests; excerpt bounds proven; live AgentOS restart still operator step |
| Evidence fidelity (TM / Griffin / SigNoz) | **60** | + P8-D: guard verdict metadata (rule/pattern_class/findings) persisted into threats/sources/signals + case files; live MCP still PARTIAL |
| Demo readiness (cold laptop → hero loop) | **58** | Run-3 rehearsal: cold bring-up + e2e + dry-run PASS, capture checklist; **live replays blocked on OpenAI quota** |
| Hackathon assets (WS11) | **38** | Capture checklist landed; screenshots/video still human — **excluded from overall** |
| **Overall (excl. WS11)** | **~64%** | Phases 5–6 + P7-A + P8 exits; **cap ≤65** until live reruns + P7-B |

**Do not claim 70%+.** Live S1/S2/S5 rerun (quota), P7-B TabFM ship, and demo capture are still open; MCP stdio still PARTIAL.

---

## 2. Area scorecard (measured, capped)

Inflation ban: move a cell only when that area’s exit in `19` §2 passes. “Code landed” ≠ exit passed.

| # | Area | Start | AM 2026-07-23 | **Measured now (PM)** | Exit status |
|---|---|---:|---:|---:|---|
| 1 | Positioning / framing | 58 | 58 | **66** | **P5-B exits met** — honesty greps 0; MAD + MCP PARTIAL in README/`14`/`06`; Beat-3 narration = MAD; `23` overview |
| 2 | HQ frontend / IA | 55 | 64 | **72** | **P6-A/P6-B exits met** — `hitl` view, threats panel, api_down recover (helper + tests); 26 FE tests in CI |
| 3 | Human APIs | 58 | 66 | **70** | Partial — + `GET /api/hitl` w/ pagination headers; threats page consumption |
| 4 | Agent APIs / tools | 64 | 66 | **72** | **P5-B/P6-B exits met** — excerpt bounds tested; A15 hatch tested; dashboards twin envelope + scope 404 |
| 5 | HQ Agent | 56 | 62 | **62** | Unchanged — no new exits this pass |
| 6 | Version timeline / pinpoint | 52 | 68 | **68** | Unchanged — no new exits this pass |
| 7 | Model explore / sims | 50 | 56 | **56** | Unchanged; corpus scorecard = explicit DEFER (P6-C, no endpoint) |
| 8 | Griffin (MAD) | 46 | 54 | **58** | **P7-A exits met** — spike re-measured (`_phase7_g7.json`), worker contract + MAD-fallback tests; runtime still MAD |
| 9 | SigNoz | 54 | 58 | **58** | Unchanged (user pin: no further polish); MCP still PARTIAL |
| 10 | Unplug coverage | 68 | 70 | **76** | **P5-A exits met** — matrix 128 rows / 0 silent gaps; S1/S2/S5 CI stubs; live rerun DEFER (quota) |
| 11 | Tests / CI / e2e | 48 | 58 | **64** | Suite grew: server 130 / agents 17 / sdk 6 / hq 26, all green in CI |
| **Overall (1–11)** | **~48** | **~57** | **~62** | Cap ≤65; live reruns + P7-B + capture still open |
| 12 | Hackathon assets | 35 | 35 | **38** | Track only — capture checklist landed; media human |

Equal-weight of areas drifts higher than the honesty pin; **authoritative overall = ~64% / ≤65%**. TabFM remains **required Phase 7** — spike measured (P7-A), ship (P7-B) not started; never claim live.

### P8 remeasure (2026-07-24) — area moves, each citing a measured exit

| # | Area | PM 07-23 | **P8 (07-24)** | Exit evidence |
|---|---|---:|---:|---|
| 2 | HQ frontend / IA | 72 | **74** | P8-A: `docs/25` graph + completeness proof (zero unknowns); loading/id fixes across 6 views; FE suite 26 → **40** green |
| 3 | Human APIs | 70 | **72** | P8-B: 404/409 = `{detail, hint}` everywhere (tested); dup version_id → 409 |
| 4 | Agent APIs / tools | 72 | **78** | P8-B: twin for EVERY HQ view + `graph_links` walkable graph + `docs/26` guide; 12 new twin tests |
| 7 | Model explore / sims | 56 | **64** | P8-C: `model_catalog` (2026-07, reasoning tiers) + additive `GET /api/agents/{id}/model-intel` — projections from recorded tokens only, rec cites DB evidence; 4 tests + live-verified vs hero DB |
| 10 | Unplug coverage | 76 | **80** | P8-D: shared `guard_factory` config; verdict metadata persisted on threats/sources/signals + case files; matrix updated; 5 new tests |
| 11 | Tests / CI / e2e | 64 | **68** | Suite grew: server 130 → **149**, sdk 6 → **8**, hq 26 → **40** (agents 17), boundaries clean |
| — | Overall (1–11) | ~62 | **~64** | Cap **≤65** holds — live S1/S2/S5 rerun (quota), P7-B TabFM ship, capture still open |

---

## 3. Measurable exits observed (2026-07-23)

### Pass (local + CI)

```text
PYTHONPATH=sdk:server:. uv run python -m unittest discover -s server/tests
PYTHONPATH=sdk:server uv run python -m unittest discover -s sdk/tests
PYTHONPATH=sdk:server:. uv run python -m unittest discover -s agents/tests
uv run python scripts/check_import_boundaries.py
cd hq && pnpm build && pnpm test
PYTHONPATH=sdk:server uv run python scripts/e2e_path_to_95.py
# CI jobs: python, e2e, hq, hq-test (PR #17)
```

P1 regression exits (must stay green):

| Exit | Test |
|---|---|
| Proxy warm does not write seed file | `WaveBGriffinStatusTests.test_proxy_warm_does_not_write_seed_file` |
| Recommend without session keeps curated order | `test_recommend_without_session_keeps_curated_order` |
| Dimension winners = majority, not last write | `test_dimension_winners_majority_not_last_write` |
| Span extract skips metadata names | `test_extract_spans_skips_metadata_names` |
| HQ recommend injects `_server()` | `test_recommend_models_injects_server_url` |
| Webhook same-ms insert does not 500 | repository bump + suite stability |

### Phase 2 exits (met on `main` via PR #17)

| Exit | Evidence |
|---|---|
| `scripts/e2e_path_to_95.py` | propose→apply(`confirm`)→pin→`version_pinpoint` + `agentos_reload_required` |
| CI `e2e` | scratch DB job green |
| HQ cascade + hash `pnpm test` | `hq/src/*.test.ts` |
| CI `hq-test` | green |
| HQ tool error matrix | timeout / 4xx / 5xx → `{ok:false,error,tool}` |

### Fail / untested (blocks further inflation)

| Gap | Why it blocks |
|---|---|
| ~~SigNoz MCP stdio hang~~ | **Phase 3:** HTTP/Query Range preferred in skills + Case File; MCP optional |
| ~~Live Fleet Health without seed~~ | **Phase 3:** cold soak script + tests (`sqlite_proxy`, no seed write) |
| Demo dry-run end-to-end | ~~Phase 4~~ — `scripts/live_ops_dry_run.py` + probe |
| TabFM / TabPFN | Not claimed; MAD only until **required** TabFM Phase 7 ([`21`](21-next-phases-plan.md)) — **code NOT implemented** |

### Phase 3 exits (met on `main` via PR #18)

| Exit | Evidence |
|---|---|
| Query Range golden fixtures | `server/tests/fixtures/query_range_*.json` + `test_phase3_evidence.py` |
| Griffin cold-path soak | `scripts/griffin_cold_soak.py` + `test_griffin_cold_soak.py` |
| HTTP before MCP | HQ Agent prompt/SKILL + Case File hints + status `mcp_note` |
| ≥3 distinct dashboard UUIDs | env + list-API unit tests |

### Phase 4 exits (met on this branch)

| Exit | Evidence |
|---|---|
| Live ops dry-run | `scripts/live_ops_dry_run.py` + `test_phase4_live_ops.py` |
| Reload honesty + probe | apply `agentos_probe`; AgentOS `/internal/runtime`; HQ banner |
| Pagination labels | HQ signals/proposals/versions/Case Files “showing N of Total” |
| Session filters e2e | `agent_version` / `version_id` in dry-run + unit tests |

### Phases 5–6 + P7-A exits (met on `main`, 2026-07-23 PM)

| Exit | Evidence |
|---|---|
| P5-A Unplug matrix | `docs/plans/unplug-coverage-matrix.md` — 128 rows (99 COVERED / 29 N/A / 0 silent); `agents/tests/test_guard_scenarios.py` + `test_unplug_coverage_matrix.py` |
| P5-B honesty + excerpts | `rg 'TabFM live\|demo badge'` → 0; excerpt-bound tests in `test_read_models.py`; A15 `full_transcript` hatch named + tested |
| P6-A HITL UI | `hq/src/views/Hitl.tsx` + `GET /api/hitl` + SSE decide; `test_hitl_api.py` + `hitl.test.ts`; honesty string UI + `14` |
| P6-B recover/threats/twins | `apiRecover.ts` + tests; `ThreatsPanel.tsx` on fleet_health; dashboards agent-view envelope + scope 404 |
| P6-C corpus | **DEFER** — no server endpoint; docs/12 P1 row contract-only |
| P7-A TabFM spike | `docs/_phase7_g7.json` (load ~54s, ~80s/series CPU, N=1 @ 360s); `tabfm_worker.py` contract + `test_tabfm_worker_stub.py` |
| Run-3 demo rehearsal | cold bring-up README-verbatim PASS; e2e + dry-run PASS; `docs/plans/capture-checklist.md` |

### Still open (blocks further inflation)

| Gap | Why it blocks |
|---|---|
| Live S1/S2/S5 rerun + hero re-verify | **OpenAI key over quota** — recorded `_phase4_g4.json` stands; rerun on top-up |
| P7-B TabFM ship | worker + degrade + honest labels — not started |
| Demo capture (screenshots/video/submission) | Track H, human |

**No further SigNoz/seed/fixture data polish** (user pin after Phase 3).

---

## 4. What works vs broken vs untested

| Component | Works | Broken / weak | Untested |
|---|---|---|---|
| Apply-model + reload flag | API returns `agentos_reload_required` + `agentos_probe`; dry-run asserts | AgentOS not restarted by server (by design) | Optional live restart screenshot |
| Griffin MAD status | Estimator=mad, honesty string, proxy in-memory | Anomaly usefulness without seed still low | Cold soak multi-cycle (Phase 3 on main) |
| Model explore | Session-scoped TM promote; majority dim winners | Explore loop off by default | Live OpenAI catalog + real replays |
| SigNoz evidence | Links + bounded spans when Query Range shape is span-like | MCP hang; key-less honest empty | Golden fixtures + HTTP prefer (Phase 3) |
| HQ Agent tools | Timeouts/errors structured; recommend uses deploy URL | Full agent conversation quality | Scripted multi-tool diagnose |
| HQ UI | Build green; MAD strip / pin UI; cascade+hash FE tests in CI | — | Manual cascade matrix |
| Webhooks | Harden tests + same-ms PK fix | — | High-volume burst soak |

---

## 5. Next plan — harden framework first (Wave C = backlog)

**Authoritative phase bundles:** [`21-next-phases-plan.md`](21-next-phases-plan.md) + run order in [`24-ship-week-plan.md`](24-ship-week-plan.md). Phases 2–6 done; P6-C explicit DEFER; P7-A spike done. **Next = P7-B (TabFM ship) + quota-gated live reruns + Track H capture.**

Order: **fix → test → measure → then new features**. Overall stays **~62% / ≤65%** until live reruns + P7-B exits.

### Top 5 concrete hardening items

1. ~~**WS9 e2e script + CI job**~~ — **Phase 2 done**
2. ~~**HQ FE cascade tests**~~ — **Phase 2 done** (`node:test` cascade + hash; CI `hq-test`)
3. ~~**Griffin cold-path soak**~~ — **Phase 3 done** (PR #18)
4. ~~**SigNoz evidence contract**~~ — **Phase 3 done** (PR #18)
5. ~~**HQ tool error matrix**~~ — **Phase 2 done**

### Explicit backlog (not % fuel)

- ~~**Phase 4 live ops loop**~~ — **done** (PR #19)
- ~~**HITL pause UI**~~ — **P6-A done**; corpus scorecard = **P6-C DEFER** (no endpoint)
- **TabFM integration (required P7-B)** — spike measured (P7-A: N=1 @ 360s cadence, async worker, MAD degrade); **runtime ship NOT started**
- WS11 hackathon capture (screenshots/video) — track only; capture checklist ready
- Claiming ≥70% overall before live reruns + P7-B exits + measured re-score
- Further SigNoz/seed/fixture polish — **stopped per user**

---

## 6. Scoreboard correction note

`docs/19` §5.2 previously listed After B **~74–80 est.** That estimate is **withdrawn**. Measured path: ~48 → ~55 → ~57 (post Phases 2–4) → **~62 (post Phases 5–6 + P7-A, this doc, 2026-07-23 PM)**. Every move cites exits in §3 above; cap **≤65** until live reruns + P7-B.
