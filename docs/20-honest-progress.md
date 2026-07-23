# ArcNet — Honest progress measurement (post Phase 2 / Phase 1 remeasure)

**Date:** 2026-07-23  
**Branch:** `main` @ PR #18 merge; Phase 4 work on `phase-4-live-ops`  
**Rule:** overall product readiness **≤60%** until measurable exits pass. No 74/80/95 theater.

Companion: [`19-path-to-95.md`](19-path-to-95.md) (plan), [`plans/path-to-95-acceptance.md`](plans/path-to-95-acceptance.md) (acceptance scripts), [`21-next-phases-plan.md`](21-next-phases-plan.md) (post–Wave B phase bundles + TabFM research).

---

## 1. Verdict

| Slice | Honest % | Evidence basis |
|---|---:|---|
| Shipped surface (APIs/UI/tools exist) | **62** | Routes, HQ views, HQ tools present; many empty/error paths thin |
| Reliability (timeouts, flakes, reload honesty) | **56** | HQ tool matrix + e2e + Phase 4 dry-run/probe; live AgentOS restart still operator step |
| Evidence fidelity (TM / Griffin / SigNoz) | **54** | Phase 3 fixtures + cold soak + HTTP-prefer on main; live MCP still PARTIAL |
| Demo readiness (cold laptop → hero loop) | **50** | Phase 4 dry-run checklist; optional restart screenshot open |
| Hackathon assets (WS11) | **35** | Separate track — **excluded from overall** |
| **Overall (excl. WS11)** | **~57%** | Phases 2–4 exits; **cap ≤60** — not 70%+ |

**Do not claim Wave B / Phase 2 reached 74/80/95.** CI gates landed; evidence trust and live ops still open.

---

## 2. Area scorecard (measured, capped)

Inflation ban: move a cell only when that area’s exit in `19` §2 passes. “Code landed” ≠ exit passed.

| # | Area | Start | After Wave A (est.) | **Measured now** | Exit status |
|---|---|---:|---:|---:|---|
| 1 | Positioning / framing | 58 | ~60 | **58** | Partial — honesty pins OK; demo chrome still mixed |
| 2 | HQ frontend / IA | 55 | ~70 | **64** | Partial — cascade/hash FE tests + `hq-test` CI (Phase 2); polish open |
| 3 | Human APIs | 58 | ~72 | **66** | Partial — pagination + HQ “showing N of Total” (Phase 4) |
| 4 | Agent APIs / tools | 64 | ~68 | **66** | Partial — envelopes + timeouts; not every twin battle-tested |
| 5 | HQ Agent | 56 | ~60 | **62** | Partial — propose→apply→pin CI + live_ops dry-run (Phase 4); TabFM not coded |
| 6 | Version timeline / pinpoint | 52 | ~78 | **68** | Partial — pinpoint fields exist; cascade polish open |
| 7 | Model explore / sims | 50 | ~62 | **56** | Partial — TM session-scoped ranking + majority winners; no corpus loop |
| 8 | Griffin (MAD) | 46 | ~48 | **54** | Partial — cold soak: no seed write, `sqlite_proxy`, status not stuck cold (Phase 3) |
| 9 | SigNoz | 54 | ~58 | **58** | Partial — golden Query Range fixtures + HTTP preferred before MCP (Phase 3) |
| 10 | Unplug coverage | 68 | ~72 | **70** | Partial — fleet + HQ Agent; ingest audit incomplete |
| 11 | Tests / CI / e2e | 48 | ~55 | **58** | **Phase 2 exits met** — e2e + hq-test + tool matrix in CI |
| **Overall (1–11)** | **~48** | **~62–68 est. (rejected)** | **~57** | Cap ≤60; Phases 2–4 ≠ 70%+ |
| 12 | Hackathon assets | 35 | — | **35** | Track only |

Equal-weight of areas drifts higher than the honesty pin; **authoritative overall = ~57% / ≤60%**. TabFM remains **required Phase 7** — not claimed.

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

**Authoritative phase bundles:** [`21-next-phases-plan.md`](21-next-phases-plan.md). Phases 2–4 done (Phase 4 on branch). Phase 1 remeasure done (~57% / ≤60%). **Next = Phase 5 (Safety matrix)**. TabFM = **required Phase 7 (not coded yet)**.

Order: **fix → test → measure → then new features**. Wave C items stay backlog until measurement exits move. Overall stays **~57% / ≤60%** — Phase 2–4 do not unlock 70%+.

### Top 5 concrete hardening items

1. ~~**WS9 e2e script + CI job**~~ — **Phase 2 done**
2. ~~**HQ FE cascade tests**~~ — **Phase 2 done** (`node:test` cascade + hash; CI `hq-test`)
3. ~~**Griffin cold-path soak**~~ — **Phase 3 done** (PR #18)
4. ~~**SigNoz evidence contract**~~ — **Phase 3 done** (PR #18)
5. ~~**HQ tool error matrix**~~ — **Phase 2 done**

### Explicit backlog (not % fuel)

- ~~**Phase 4 live ops loop**~~ — **done on branch** (dry-run + pagination labels + probe)
- Wave C feature expansion (corpus scorecard, HITL pause UI polish)
- **TabFM integration (required Phase 7)** — HF `google/tabfm-1.0.0-pytorch` `regression/`; MAD degrade OK; TabPFN deferred — **NOT implemented**
- WS11 hackathon capture (screenshots/video) — track only
- Claiming ≥70% overall before Phase 5+ exits + measured re-score
- Further SigNoz/seed/fixture polish — **stopped per user**

---

## 6. Scoreboard correction note

`docs/19` §5.2 previously listed After B **~74–80 est.** That estimate is **withdrawn**. Measured baseline was **~55%**; post–Phase-2/3 remeasure is **~57%** (this doc). Future PRs update only by citing exits in §3 above.
