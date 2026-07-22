# ArcNet — Honest progress measurement (post Wave B P1 fixes)

**Date:** 2026-07-23  
**Branch:** `wave-b-path-to-95` (PR #16)  
**Rule:** overall product readiness **≤60%** until measurable exits pass. No 74/80/95 theater.

Companion: [`19-path-to-95.md`](19-path-to-95.md) (plan), [`plans/path-to-95-acceptance.md`](plans/path-to-95-acceptance.md) (acceptance scripts), [`21-next-phases-plan.md`](21-next-phases-plan.md) (post–Wave B phase bundles + TabFM research).

---

## 1. Verdict

| Slice | Honest % | Evidence basis |
|---|---:|---|
| Shipped surface (APIs/UI/tools exist) | **62** | Routes, HQ views, HQ tools present; many empty/error paths thin |
| Reliability (timeouts, flakes, reload honesty) | **54** | HQ tool errors/timeouts + apply reload flag; webhook same-ms flake fixed; no e2e |
| Evidence fidelity (TM / Griffin / SigNoz) | **52** | P1 attribution/span/proxy fixes landed + unit tests; live SigNoz/MCP still PARTIAL |
| Demo readiness (cold laptop → hero loop) | **48** | Heroes + seed scripts exist; operator e2e not automated |
| Hackathon assets (WS11) | **35** | Separate track — **excluded from overall** |
| **Overall (excl. WS11)** | **~55%** | Equal-weight of first four slices ≈ 54; areas 1–11 below ≈ **55** |

**Do not claim Wave B reached 74/80/95.** Surfaces shipped; trustability did not.

---

## 2. Area scorecard (measured, capped)

Inflation ban: move a cell only when that area’s exit in `19` §2 passes. “Code landed” ≠ exit passed.

| # | Area | Start | After Wave A (est.) | **Measured now** | Exit status |
|---|---|---:|---:|---:|---|
| 1 | Positioning / framing | 58 | ~60 | **58** | Partial — honesty pins OK; demo chrome still mixed |
| 2 | HQ frontend / IA | 55 | ~70 | **62** | Partial — cascade/reload UI present; FE tests absent |
| 3 | Human APIs | 58 | ~72 | **64** | Partial — pagination/write secret exist; not all filters proven |
| 4 | Agent APIs / tools | 64 | ~68 | **66** | Partial — envelopes + timeouts; not every twin battle-tested |
| 5 | HQ Agent | 56 | ~60 | **58** | Partial — tools + Unplug; propose→apply→pin e2e not CI |
| 6 | Version timeline / pinpoint | 52 | ~78 | **68** | Partial — pinpoint fields exist; cascade polish open |
| 7 | Model explore / sims | 50 | ~62 | **56** | Partial — TM session-scoped ranking + majority winners; no corpus loop |
| 8 | Griffin (MAD) | 46 | ~48 | **52** | Partial — proxy no longer freezes as seed; useful anomaly UX still thin |
| 9 | SigNoz | 54 | ~58 | **56** | Partial — bounded evidence + span filter; MCP hang remains |
| 10 | Unplug coverage | 68 | ~72 | **70** | Partial — fleet + HQ Agent; ingest audit incomplete |
| 11 | Tests / CI / e2e | 48 | ~55 | **52** | Partial — unit green incl. Wave B P1s; **no** seed→check e2e; no FE job |
| **Overall (1–11)** | **~48** | **~62–68 est. (rejected)** | **~55** | Cap ≤60 until exits pass |
| 12 | Hackathon assets | 35 | — | **35** | Track only |

Equal-weight average of measured areas 1–11 ≈ **55%** (rounded). User-aligned ceiling: **≤60%**.

---

## 3. Measurable exits observed (2026-07-23)

### Pass (local)

```text
PYTHONPATH=sdk:server:. uv run python -m unittest discover -s server/tests   # 79 OK (incl. Wave B P1s)
PYTHONPATH=sdk:server uv run python -m unittest discover -s sdk/tests       # 6 OK
PYTHONPATH=sdk:server:. uv run python -m unittest discover -s agents/tests  # 4 OK
uv run python scripts/check_import_boundaries.py                            # clean
cd hq && pnpm build                                                         # OK
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

### Fail / untested (blocks % inflation)

| Gap | Why it blocks |
|---|---|
| No `scripts/e2e_path_to_95.py` (or equiv) in CI | Cannot prove propose→apply→pin→check |
| No HQ FE unit/Vitest job | Cascade/reload UI unverified in CI |
| SigNoz MCP stdio hang | Deep evidence path PARTIAL |
| Live Fleet Health without seed | Proxy path unit-tested; not operator-observed cold |
| Demo dry-run end-to-end | Not run in this measurement pass |
| TabFM / TabPFN | Correctly **not** claimed; MAD only |

---

## 4. What works vs broken vs untested

| Component | Works | Broken / weak | Untested |
|---|---|---|---|
| Apply-model + reload flag | API returns `agentos_reload_required` | AgentOS not restarted by server (by design) | Live AgentOS reload UX |
| Griffin MAD status | Estimator=mad, honesty string, proxy in-memory | Anomaly usefulness without seed still low | SigNoz series source path |
| Model explore | Session-scoped TM promote; majority dim winners | Explore loop off by default | Live OpenAI catalog + real replays |
| SigNoz evidence | Links + bounded spans when Query Range shape is span-like | MCP hang; key-less honest empty | Real Query Range against cloud |
| HQ Agent tools | Timeouts/errors structured; recommend uses deploy URL | Full agent conversation quality | Scripted multi-tool diagnose |
| HQ UI | Build green; Fleet Health MAD strip / HQ Agent pin UI | FE tests none | Manual cascade matrix |
| Webhooks | Harden tests + same-ms PK fix | — | High-volume burst soak |

---

## 5. Next plan — harden framework first (Wave C = backlog)

**Authoritative phase bundles:** [`21-next-phases-plan.md`](21-next-phases-plan.md) (Phase 1 = this planning pass; execution starts Phase 2).

Order: **fix → test → measure → then new features**. Wave C items stay backlog until measurement exits move.

### Top 5 concrete hardening items

1. **WS9 e2e script + CI job** — seed DB → propose → apply(`confirm`) → pin → `check` asserts `version_pinpoint` + reload flag; fail CI on regression.
2. **HQ FE cascade tests** — Vitest for Agent→version→model→session reducer + deep-link hash; add `pnpm test` to CI.
3. **Griffin cold-path soak** — no seed file: N loop cycles keep `series_source=sqlite_proxy`, status not stuck `cold`, Fleet Health shows warmth strip without seed theater.
4. **SigNoz evidence contract** — golden fixtures for Query Range shapes; MCP hang documented + HTTP fallback always preferred in HQ Agent instructions/skills.
5. **HQ tool error matrix** — each tool: timeout / 4xx / 5xx → stable JSON envelope; recommend/propose always carry `evidence_refs` or explicit empty reason.

### Explicit backlog (not % fuel)

- Wave C feature expansion (corpus scorecard, TabPFN path, HITL pause UI polish)
- WS11 hackathon capture (screenshots/video) — track only
- Claiming ≥70% overall before e2e + FE tests green

---

## 6. Scoreboard correction note

`docs/19` §5.2 previously listed After B **~74–80 est.** That estimate is **withdrawn**. Replace with measured **~55%** (this doc). Future PRs update §5.2 only by citing exits in §3 above.
