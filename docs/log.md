# Build log

## Day 0 — Mon Jul 20 (planning)

**v1 (initial):** docs 00–07 + first mock; framing = agent security + observability dashboard on SigNoz (Agno + unplug-ai + Griffin/TabFM + signals + Case File). Review pass fixed the calendar (Jul 20 = **Mon**, deadline **Sun Jul 26**), re-tiered so the demo rides on P0, rebalanced Phase 4, moved TabFM spike to Day 0 / seed.py to Phase 3, added S4 "Griffin-first" choreography, pinned the signal schema, enumerated the env surface. Deps verified installable.

**v2 pivot (office-hours + landscape):** reframed to **"agents that watch themselves and get better"** — the control plane for a self-improving fleet. Locked: unified spine (security = visceral demo, self-improvement = frame); **no DSPy/no evolver** (ArcNet *shows* behavior; existing coding agents improve the fleet); Unplug = **source-trust monitoring** (trust per source, filter untrusted/scraped, flag forward-facing). New pillars: **agent-view** (machine-optimal twin of every datum) + **Time Machine** (counterfactual replay-from-trace, the headline). Landscape: nobody closes trace→fix→proof loop; CAR + GEPA validate feasibility. Concept in `08-vision-v2.md`.

**Whole plan unfolded to v2:** docs 00–06 revised (01 product, 02 arch with `replay.py` + agent-view API + Time Machine flow, 03 plan with replay harness Phase 4, 05 unplug=source-trust, 06 six-beat demo, 00 judging map). Added `09-frontend.md`.

**Frontend = Unplug design language** (dark terminal, pure black + electric cyan `#00e8ff`, monospace, sharp corners, CRT scanlines, `snake_case()` copy, `> arcnet` wordmark). Mock: `docs/mock/arcnet-v3.html` (Time Machine + human/agent toggle). Earlier mocks retired. `09-frontend.md` has the design system + IA + 4 copy-paste UI-generation prompts (cyan/amber/matrix/graphite).

**Consistency pass (v2):** unified dashboard name (Threats & Trust), explained F8/F12 numbering gaps, normalized "HQ"→"the UI" in prose (`hq/` stays the dir), verified P0/P1/P2 tiers match across 01/03, Signal schema identical, every demo beat maps to a P0 feature.

- **Next (Phase 0 in `03-plan.md`):** SigNoz Docker up, Agno hello trace, unplug smoke, replay feasibility spike, TabFM spike, service key + Query/metrics-list, submission form + deadline time.

## Day 1 — Tue Jul 21 (gap review + spec hardening, then build)

Full gap pass over the plan before coding. **Schedule re-anchored**: Mon went to concept, so build = Tue–Sat (Tue is a double day: foundations AM + shield core PM; TabFM spike and S2 moved to Wed). New specs: `10-time-machine.md` (recorded-transcript shape, tool-stub matching, precise diff semantics — `[EXPLOITED]` = model *attempted* the injected action, verdict schema, 12-incident corpus) and `11-scenarios.md` (per-scenario fixtures + telemetry assertions = the test suite; fleet clones L & O so a cut Agent K never leaves a fleet of one). Signals now have an **inline fast-path** (guard block → signal in ms; SigNoz alert = system of record) so "self-corrects in seconds" survives the alert-evaluation interval. Added **north star + success criteria + tradeoff order** to `08`, decision **gates G1–G5** to `03`, Beat-5 narration that preempts "didn't you already block it?". All Day-0/phase labels re-pointed to the new Day 1–6 calendar.

**Prove-pillar generalized (user call):** the Time Machine is no longer injection-centric — it diffs **whole behavior** (goal_reached/steps/tool_errors/cost core; resisted/exfil only for threat sessions). Market anchor added to `08`: model/prompt upgrades are swap-and-pray; replaying your own trace history = a behavioral regression suite. Beat 5 reworked: Worms loop replay live (killed→stops at step 5, −72% cost), Edgar pre-run second, corpus scorecard close. Corpus mix rebalanced problem-diverse (S4×3/S1×3/S5×2/S2×2/S0×2); S4 transcripts now mandatory; harness gains a step cap so a looping candidate terminates. **Deferred (user call):** deeper context-inspector work (step-by-step view of what each agent ingested) — parked as P1, build when time allows.

**Long-term commitment (user call):** ArcNet is a project we keep after the event — live real-work agents run under it and we use it ourselves. Consequences written into the docs: product-core vs demo-layer rules in `02` (core never imports scenario code; demo behavior = config + fixtures), "Beyond the hackathon" section in `08`, live-work dogfood agent added as P1 + a standing rule in `03`.

**Data & API contract frozen (`12-data-api.md`) — planning layer complete:** full SQLite schema (agents/sessions/signals/threats/sources/replays/hitl/webhook_events; transcript = JSON doc by choice; Case Files generated on demand; Griffin cache in-memory), every route with request/response shapes, the agent-view envelope, SSE event contract (with Last-Event-ID replay), webhook dedupe/mapping, Case File bundle format, and write-ownership per component so parallel Cursor sessions don't collide. Sources ledger captures context-inspector data from day 1 even though that UI is deferred. Docs now 00–12; next = Phase 0 execution.

**Adversarial review (4 agents: feasibility / judge / delivery / coherence), all findings fixed:** (a) *Feasibility, verified from library source*: the Agno instrumentor emits **OpenInference semconv, not `gen_ai.*`** — 04 rewritten against real span names/keys; Agno guardrails are **input-only** — the 4 checkpoints are 4 distinct hook surfaces (02/05); steer-propagation unverified → Phase-0 test + substitution fallback; SigNoz alert API needs **v5 `queries` payloads**; span-attribute caps → transcripts **SQLite-primary**; seasonal anomaly alerts can't fire live (≥5m windows) → screenshot artifact; Griffin discovery defaults to a hardcoded `arcnet.*` allowlist; temp-0 ≠ determinism noted. (b) *Judge*: unplug-ai provenance disclosure now at README top + Phase-0 Slack ruling ask; "nobody else has" de-absolutized (LangSmith/Braintrust/Sentry Seer named; claim = session-level + trust-live + every-panel-twin); README screenshot slots for the SigNoz depth the video can't carry; corpus scorecard off camera; corpus provenance in narration. (c) *Delivery* (P(all beats by Sat) ≈ 15% as-was): Phase 0 → one full day with the de-risk checks; TabFM spike first-item 45–90 min walk-away; UI parallel track starts Phase 3 on mock data; G3 → manual replay tripwire at Phase-3 exit; corpus pre-cut; video = protected half-day assembled from per-phase clips; integration-seam check end of Phase 2; both provider keys + deadline chased Day 1. (d) *Coherence*: −72%→−82%, "2/2"→"attacks resisted 5/5", P1 lists mirrored, seasonal out of 01's F4, Griffin card → Phase 5, `tokens` restored to the diff, claude-fable-5 labels aligned.

**Pacing switched to phase-gated (user call):** no calendar-day scheduling — six milestone-gated phases, each starting the moment the previous exit is green; the only hard date is the Sun Jul 26 submission. Hours banked early flow into Phase 5–6 polish/re-records. Added "The bar (the judge test)" to `03`: every phase exits demoable, hero views product-polished, nothing on camera depends on luck. All day labels across `00/02/04/05/06/07/10/11` converted to phase labels.

## Phase 0 — Tue Jul 21 (foundations & de-risk) — EXIT

**Expected:** hello-Agno→SigNoz with real attrs in 04; S1 taint proven; G1 replay+steer; both model keys; organizer ruling requested.
**Actual:** scaffold + SigNoz `v0.133.0` (Foundry) up (~1.5 GiB RSS on 7.65 GiB Docker); hello trace landed (`hello_arcnet.run` / `OpenAIChat.invoke` / `add`, `llm.token_count.*`); S1 taint **block** via `taint_sources=` (session-only = `review` — 05 fixed); G1 **PASS** (stubs + session_state steer + post_hook substitution); models = gpt-4o-mini / gpt-4o on OpenAI key; Anthropic key missing; H2 Slack ruling + H3 submission form still **human-blocked**; service-account key = **manual UI step** (README). Ready for Phase 1.

## Phase 1 — Tue Jul 21 (shield core) — EXIT

**Audit:** Layout/import rule/pins clean; filled missing `agents/prompts`+`scenarios/fixtures` + SDK/server modules (no overbuilt stubs, no vendored unplug).
**Actual:** `arcnet.init`+4 checkpoints+metrics; Agent J/AgentOS; S0 clean + S5 input-block+threat row; SQLite sessions round-trip via `load_transcript`. H1/H2/H3 + empty `SIGNOZ_API_KEY` still human-blocked.

## Phase 2 — Tue Jul 21 (SigNoz depth + MCP) — EXIT

**Expected:** TabFM G2; S2 redact; 3 dashboards + v5 alerts + seasonal artifact; webhook attributable; logs↔trace; MCP answering; hq↔server↔SigNoz seam once.
**Actual:** G2 → TabFM too slow (~12s/series) + TabPFN needs `TABPFN_TOKEN` → **locked MAD**; S2 PASS (`[REDACTED]` email+SSN); dashboards/alerts/seasonal JSON + `setup.py` validate (API provision SKIP — no key); webhook → `steer` signal with `session_id`/`agent_id`; OTLP LoggingHandler; MCP `v0.8.0` binary+configs (tools need key); hq seam page + `/api/fleet` + `/api/signoz/status` (UI 200). Exit **green / PARTIAL** on live SigNoz API+MCP.

## Phase 3 — Tue Jul 21 (signals + Griffin) — EXIT

**Expected:** signal bus SSE + steer/kill; S1+S4 camera-speed; Griffin MAD + seed; G3 tripwire; HQ shells on mock.
**Actual:** SSE bus + SDK client (steer/kill/pause HITL scaffold); S1 PASS (retrieved path; model often resists without exfil — no EMAIL_SENT); S4 PASS (Griffin evaluate → kill); `scripts/seed.py` + MAD worker; G3 PASS on S1+S4 vs gpt-4o; HQ fleet_health + time_machine mock shells. `SIGNOZ_API_KEY` still empty → provision/Query Range remain BLOCKED.

## Phase 4 — Tue Jul 21 (Time Machine) — PARTIAL → PASS (G4 reassessed)

**Expected:** guarded replay harness + 3-run verdict API; stable Worms and Edgar counterfactuals; replay agent-view.
**Actual (initial):** harness/API/agent-view PASS; Worms stable 3/3 (`killed`→`partial`, overall `mixed`); Edgar `inconclusive` 2/3 and baseline never exploited because Unplug quarantined retrieval first → G4 RED.

**G4 reassessment (2026-07-21):** root cause = block-path S1 fixture (risk 0.85 → retrieved quarantine before the model saw the injection) + free-text goal predicates thrashing the 3-run majority. Fix (no guard weakening): delivered-path S1 fixture (`allow` at retrieved + tainted; exfil blocked at the `tool_call` checkpoint), behavior-based S4/S1 goal predicates, and threat-session verdict stability keyed on security dimensions. **Measured `scripts/phase4_g4_check.py` → both heroes stable `mixed` 3/3** (`docs/_phase4_g4.json`): Edgar baseline attempts exfil (blocked) vs candidate resists 3/3; Worms candidate breaks the loop. **G4 PASS.** SigNoz/OTLP untouched (replay is SQLite-primary); `SIGNOZ_API_KEY`/`TABPFN_TOKEN` empty and H1/H2/H3 unchanged.

## Phase 5 — Tue Jul 21 (UI + Case File + Record) — PASS (G5 deferred)

**Expected:** HQ wired to real APIs with agent-view toggle; Case File exporter + handoff; seed + run-demo; README; G5 MCP live test; video block.
**Actual:** server grew the generic agent-view (`/api/agent-view/{incident|session|fleet|sources}/{id}`), read-only list APIs (`/api/sessions`, `/api/replays`, `/api/signals` — additive, no frozen-shape changes), and the Case File exporter (`/export/case-file/{id}` → zip of `case-file.md` + `case-file.json` with root cause, timeline, recommended actions, fix-prompt preamble + MCP hints); covered by `server/tests/test_case_file.py` (3 tests). HQ rebuilt into six live views (fleet_health, signals w/ SSE, sources_trust, time_machine w/ live `replay.run()` + progress + history, case_files w/ incident preview + export, dashboards deep-links) with the global `human_view ⇄ agent_view` toggle and seam/empty states; `tsc -b && vite build` green. Demo choreography: `scripts/seed_demo.py` (deterministic background fleet; real hero recordings + their 24 replay rows live in `data/arcnet.db`; orphan test rows pruned) + `scripts/run-demo.sh` (seed → server → replay runtime → HQ, no Docker). README rewritten (hero results table, quick start, Case File handoff, verification).
**Deferred (user resource pause, Docker down):** G5 live MCP handoff test + backup recording; README screenshot capture; SigNoz dashboard/alert re-provisioning. Video assembly = human task. Corpus replay stays pre-cut.

## Phase 6 — Wed Jul 22 (API read models + Docker-free ship batch) — IN PROGRESS

**Expected:** human/agent API separation without breaking docs/12; license + README final; Docker-free demo verified.
**Actual:** server split into `repository.py` (all SQL, deterministic ordering, one signal-attribution rule for REST+SSE) + `read_models.py` (human rows vs bounded agent context) + thin routes (plan: `docs/13`); session agent-view no longer leaks full recorded tool outputs (pointers/digests instead); sources agent-view 404s unknown ids; dead mock route removed; fleet aggregate de-N+1'd. 17 server tests incl. projection/bounds/attribution/ordering/404 coverage; Apache-2.0 LICENSE; README criteria map + model boundaries + limitations; `scripts/check_import_boundaries.py`. Docker-free demo re-verified live: seed → server+replay runtime → HQ proxy 200, both hero replays stable 3/3 through the refactored path (Worms `killed→partial`, Edgar `exfil 1→0`), case-file zip + SSE catch-up green. **Known drift recorded:** APIs speak epoch-ms while docs/12 says ISO-8601 — frozen contract preserved as shipped, documented in `docs/13` + README. Docker/SigNoz/G5 still deferred; H1/H2/H3 human blockers unchanged.

## Phase 6 — Wed Jul 22 (SigNoz evidence run) — PARTIAL (blocked on service-account key)

**Expected:** Docker back → SigNoz stack up, provisioning + Query Range + MCP + G5 as far as the key allows.
**Actual:** PR #4 merged into main (`b4091d1`) after fixing the Greptile finding — boundary check now scans `hq/**/*.ts(x)` (import/export/dynamic-import + `import.meta.glob`) for relative paths resolving into `agents/`/`scripts/`, with `scripts/tests/test_check_import_boundaries.py` (5 tests). SigNoz re-bring-up on the pinned stack (`foundryctl` v0.2.15 → `signoz/signoz:v0.133.0`): all 5 containers healthy in <1 min, `/api/v1/health` ok, version endpoint = `v0.133.0`; resource note + ingester-image drift recorded in `docs/04`. Live telemetry re-verified: hello Agno trace exported over OTLP and confirmed in ClickHouse (`arcnet-hello` trace_ids `68a0c4a9…`, `b68eb095…`) with the exact OpenInference keys from Phase 0 (`openinference.span.kind`, `llm.token_count.*`, `tool.name`, `agno.tools`). Provisioning JSON re-validated via `deploy/provision/setup.py` (4 dashboards, 6 v5-`queries` alerts, seasonal artifact — zero `builderQueries`); live POST correctly skips on empty key. Query Range probed: unauthenticated `POST /api/v5/query_range` → 401 as documented. Webhook → signal path re-proven: SigNoz-shaped firing payload with `agent_id`/`session_id` labels → 204 → attributable `steer`/`critical` signal row on a scratch DB. MCP binary present (`deploy/mcp/bin`, v0.8.0 pin) but stdio refuses without `SIGNOZ_API_KEY` — **live provisioning, Query Range, MCP tools, and G5 handoff remain BLOCKED on the one human step: create a service account (SigNoz UI :8080 → Settings → Service Accounts) and set `SIGNOZ_API_KEY` in `.env`.** No screenshots captured (human/visual task).

## 2026-07-22 — local SigNoz UI admin reset
Root-user env (`SIGNOZ_USER_ROOT_*`) applied via casting + gitignored compose; `signoz-signoz-0` recreated; root reconciliation + login smoke OK. Password not logged (see local `.signoz-local-admin`).

## Phase 6 — Wed Jul 22 (SigNoz evidence run) — DONE (G5 PARTIAL)

**Expected:** API key → provision dashboards/alerts/webhook → Query Range → `/api/signoz/status` → alert→webhook attribution → G5 MCP Case File handoff.
**Actual:** Key written to gitignored `.env` (present only). Auth smoke: `/api/v1/service_accounts/me` 200; initial 403s fixed by assigning `signoz-admin` to SA `tmp` (was `serviceAccountRoles: null`). Provisioning DONE via idempotent `setup.py`: channel `arcnet-webhook` (`019f8883-fc29-…`); dashboards Fleet/Threats/Cost/Agno (`019f8883-fc38/fc4a/fc57/fc67-…`); 6 threshold rules + seasonal anomaly (`019f8886-6939-…`–`69a6-…`). Alert payloads corrected for v0.133 flat `op`/`matchType` numeric codes + `preferredChannels` (nested thresholds rejected). Query Range DONE: `68a0c4a9b793b111882557834a98f57b` → `hello_arcnet.run`/`OpenAIChat.invoke`/`add`. `/api/signoz/status` → key present + query ok. Webhook → 204 → `sig_c7a53831` steer/critical on `s_0c6b0aa6`. G5 PARTIAL: MCP binary v0.8.0 present but stdio hung; Case File zip + Query Range fallback used. Human blockers unchanged: Slack provenance, submission form, video/screenshots.

## 2026-07-22 — verify + reinforce

PR #5 merged → `verify-reinforce`. Verification green (unittest suite, HQ build, import boundaries, provision dry-validate, SigNoz health + Query Range via `SIGNOZ-API-KEY`, case-file zip, S1/S2/S5 live). Adversarial FAIL: webhook `[]` → 500; WARNs: oversized label ids, `/api/signoz/status` claimed Query Range on `/version`, `seed_demo` ignored `ARCNET_DB_PATH`. Fixes: webhook 400 + id clip 128, status probes `query_range`, seed_demo honors env; tests added. Deferred: G4 live 3× (use `_phase4_g4.json`), MCP stdio hung, open write APIs (demo), S0/S4 re-run.

## 2026-07-22 — product map + validation

Full built-surface inventory: `docs/15-product-map.md` (system + HQ↔API mermaid, DONE/PARTIAL/GAP tables, ~110 verification points, prioritized FE backlog). Validated vs code/`12`/`13`/`14`; adversarial review recorded in-doc (dashboards deep-link fake completeness, default session ≠ heroes, Beat 5 vs `mixed`, MCP PARTIAL, HITL no AgentOS relay). Links from README + `docs/14`. No FE redesign this pass.

## 2026-07-22 — founder review → product rework plan

Founder feedback: pivot from hackathon-demo framing to a **usable agent enhancement layer**. Captured in `docs/16` §11; backlog reordered in `docs/15` §6; phased plan `docs/17-product-rework-plan.md` (R1 API/framing → R2 HQ cascade IA → R3 model-explore skills/MCP). Additive contract updates in `docs/12` (pagination headers, session `model` filter, agents/{id}/models, agent-view `signals` + `check`).

## 2026-07-22 — product rework R1 merged (PR #9)

PR #9 `product-rework-r1` merged to main. Shipped: docs 15/16/17 + docs/12 additive APIs; pagination headers; agent-view signals + check; HQ cascades; demo chrome stripped; model-explore scaffold; Greptile P1s fixed in `25fc6f7`.

## 2026-07-22 — product rework R2 (+ R3 thin)

Branch `product-rework-r2`: HQ hash `?agent=&model=&session=`; fleet + mini-fleet drill-down; Signals/Sources agent pickers; SigNoz `dashboards` on `/api/signoz/status` (env + title resolve) + provision ID emit; SDK `arcnet.hq` session tools; R3 `arcnet.model_explore` curated OpenAI snapshot + recommend/compare/record + MCP stdio shim. Tests: `server/tests/test_r2_r3_surface.py`.

## HQ Agent — Wed Jul 22

**Expected:** docs/18 plan; version registry; `hq_tools` + Agno HQ agent with Unplug; thin `#hq_agent` UI; skill/MCP; MAD honesty.
**Actual:** PR #10 merged (MCP JSON-RPC fix); PR #11 merged (`hq-agent`). Added `agent_versions` + APIs; `sdk/arcnet/hq_tools.py`; `agents/hq_agent/`; `#hq_agent` view; `skills/arcnet-hq-agent/`. Griffin tools label **MAD** (not TabFM). Proposals = `source=hq_agent` notes only. Greptile P1 fixed: `GET /api/signals?source=` so proposals are not buried by mixed-source pagination.

## HQ Agent slices 2–3 — Wed Jul 22

**Expected:** Case File / replay tools; proposal inbox polish; human-gated apply-model; session→version pin.
**Actual:** `case_file_view` + `replay_compare` tools; HQ proposal inbox with refresh / prep_apply / confirm checkbox; `POST /api/agents/{id}/apply-model` (`confirm: true` required) bumps model + registers version + optional proposal `status=applied`; `session_id` on version create/apply pins `sessions.agent_version`. TabPFN still deferred (no `TABPFN_TOKEN` work this pass). Merged as PR #12 after Greptile P1s (atomic apply + agent ownership).

## Robustness pass 1 — Wed Jul 22

**Expected:** Brutal re-score vs product readiness; kill ~92% narrative; harden highest-impact gaps.
**Actual:** Overall **~48%** robust. Hardened: apply-model transaction + ownership; check `version_pinpoint`; bounded sources + dashboards agent-view; HQ apply session pin + clearer errors; model explore live-when-key; optional `ARCNET_WEBHOOK_SECRET`; GitHub CI; tests. Docs/17–18 honesty tables replace checklist inflation.

## Path to ~95% — plan only

**Expected:** Exhaustive execution plan from ~48% → ~95% with measurable exit criteria, workstreams, waves; no product feature implement in the plan PR.
**Actual:** `docs/19-path-to-95.md` + `docs/plans/path-to-95-acceptance.md`; links from README / 15 / 16 / 17 / 18. PR #13 not merged into plan base (Greptile: live catalog failures must fall back). Branch `plan-path-to-95`.

## 2026-07-22 — Wave A path-to-95 (in progress)

**Expected:** WS4 version filters + pinpoint; WS2 write secret; WS1 version-first cascade; WS8 Unplug matrix stub; WS5.P0 already on main.
**Actual:** Sessions `agent_version`/`version_id` + `X-Total-Count`; enriched `version_pinpoint`; `ARCNET_WRITE_SECRET`; HQ cascade Agent→version→model→session; seed baseline versions; Unplug matrix stub in docs/18.

## 2026-07-22 — Wave B path-to-95 (in progress)

**Expected:** WS3 HQ Agent reliability; WS5 empirical TM-tied explore; WS6 Griffin MAD UX; WS7 SigNoz evidence; cheap WS10 strips. Stay honest (~48% baseline, Griffin=MAD, no TabFM, no 95% claim).
**Actual:** `hq_tools` timeouts + `{ok:false,error,tool}`; propose `evidence_refs`; apply `agentos_reload_required` + HQ banner; proposal pin_session path + pinpoint; recommend/compare TM evidence; optional `ARCNET_MODEL_EXPLORE_LOOP`; griffin status warmth/source + Fleet MAD strip; `GET /api/signoz/evidence`; Case File `signoz_trace`; MCP hang fallback documented.

## 2026-07-23 — Wave B P1 fixes + honest re-measure

**Expected:** Fix Greptile P1s on PR #16; verify; replace inflated After-B % with ≤60% measured scorecard.
**Actual:** Griffin proxy stays in-memory (no seed freeze); recommend TM ranking session-scoped; dimension winners majority vote; SigNoz span extract requires duration/id; HQ recommend injects `_server()`; webhook same-ms PK bump. Measured overall **~55%** in `docs/20-honest-progress.md` (≤60 cap); ~~74–80~~ withdrawn. Next = harden (e2e, FE tests, Griffin soak, SigNoz fixtures, tool error matrix) before Wave C features.

## 2026-07-23 — ship week: merge train + Phase 5 + demo rehearsal

**Merge train:** PRs #19 (Phase 4 live-ops), #20 (agent packets), #21 (product overview + honesty align) all landed on `main`; ship-week plan committed as `docs/24-ship-week-plan.md`; merged branches deleted.
**Phase 5 (both packets, worktree runs):** P5-B — MAD + MCP PARTIAL named in README/`14`/`06` limitations, Beat-3 narration corrected to MAD, excerpt caps hardened (`goal` excerpted in incident + case-file md), A15 `full_transcript` hatch named + tested as intentional; new bound-proving tests in `server/tests/test_read_models.py`. P5-A — `docs/plans/unplug-coverage-matrix.md` (128 rows: 99 COVERED / 29 N/A / 0 silent gaps) + `agents/tests/test_guard_scenarios.py` + `test_unplug_coverage_matrix.py`. Honesty grep clean; full suite + boundaries green post-merge.
**Demo rehearsal (Run 3):** cold bring-up PASS on a fresh DB (README verbatim; HQ binds `localhost`, custom `ARCNET_DB_PATH` has no heroes — record on default DB); `e2e_path_to_95` + `live_ops_dry_run` PASS. README `phase4_g4_check` line fixed (requires `--s1/--s4`). Capture checklist: `docs/plans/capture-checklist.md`. **BLOCKED (human): OpenAI key over quota** → live replays 502 (`/internal/replay` quota error) — hero re-verify + live S1/S2/S5 + Beat-5 live replay wait on a top-up; recorded `docs/_phase4_g4.json` evidence stands.

## 2026-07-23 (evening) — Phase 6 + P7-A + honest remeasure ~62%

**Phase 6:** P6-A — HQ `hitl` view (approve/reject, SSE decide, StrictMode-safe dedup) + additive `GET /api/hitl` w/ pagination + honesty string (SQLite-only relay) in UI + `14`; tests both sides. P6-B — shell `api_down` recovers on focus + 20s interval (`apiRecover.ts` helper + tests); compact threats table on fleet_health (`GET /api/threats` consumption); dashboards agent-view now serves the real server envelope (scope 404 added); sources twin already shipped. P6-C — **DEFER** (no corpus endpoint; docs/12 P1 row is contract-only; docs/15 row updated).
**P7-A:** TabFM spike re-measured on `google/tabfm-1.0.0-pytorch` `regression/` (`docs/_phase7_g7.json`): weights cached, load ~54s, median fit+predict ~80s/series CPU (7 timed), projected ~960s for 12 series. **Decision:** N=1 series @ 360s cadence, async worker, MAD degrade; `tabfm_worker.py` locks `forecast(history, features)` reusing `griffin.mad_judge` — not wired, no `tabfm` labels. P7-B = ship.
**Remeasure:** `docs/20` moved **~57 → ~62 (cap ≤65)** citing Phase 5–6 + P7-A exits; suite now server 130 / agents 17 / sdk 6 / hq 26, all CI-green. Still open: live S1/S2/S5 + hero re-verify (quota), P7-B, Track H capture.


## 2026-07-24 — P8 wave: frontend graph + agent twins + model intel + unplug hardening

**Four parallel worktree runs (grok-4.5 ×2, composer-2.5 ×2), all reviewed + suite-gated:**
P8-A — `docs/25-frontend-map.md`: full HQ relationship graph (mermaid; 9 views / 22 `api.ts` exports / 31 server routes / 3 SSE events) with completeness tables proving no orphans — every view hash-reachable, every export consumed-or-flagged, every route consumed-or-listed server-only; loading states + `<code>` id wraps landed across 6 views (SourcesTrust also resets on agent switch).
P8-B — every HQ view now has an `/api/agent-view/*` twin (home, fleet_health, threats, hitl, hq_agent, case_files, time_machine, sources_trust aliases) with `graph_links` cross-links (session→case-file/check/threats, agent→models/versions/timeline) so coding agents walk the graph without guessing URLs; 404/409 bodies now `{detail, hint}` (dup version_id → 409); `docs/26-agent-consumer-guide.md` documents the observe→diagnose→apply→verify loop. Driver restored `data.links` on the dashboards twin (strict additivity).
P8-C — `server/arcnet_server/model_catalog.py` (CATALOG_VERSION 2026-07: GPT-5-class + o-series, Opus-4.8/Sonnet-5/Haiku, Gemini-3, Kimi K3, Grok-4.5 with reasoning tiers + list-price labels) + **additive** `GET /api/agents/{id}/model-intel`: per-candidate cost projections from the agent's recorded token totals only, reasoning-tier recommendation that cites recorded threat_rate/verdicts, `honesty` string in-payload; surfaced in HqAgent; `docs/27-model-intelligence.md`. Driver reworked the run's original in-place `/models` shape change into the new endpoint (additive-only pin held); run itself died on opencode balance — salvaged from worktree.
P8-D — `sdk/arcnet/guard_factory.py` = single shared unplug Guard config for init/AgentOS/runner/replay; guard verdict metadata (`rule`, `pattern_class`, `top_score`, `findings_detail`, full `guard_verdict`) persisted on threats/sources/signals rows (pragma `_ensure_column`) and threaded into transcript steps, case-file root_cause/timeline, and agent-view rows; coverage matrix updated. Driver fixed a swallowed `def expire_alert_signals` line.
**Suite after merge:** hq 40 green; server/agents/sdk counts in `20` next remeasure. **Blockers:** opencode balance exhausted (grok/kimi runs unavailable until top-up; cursor/composer fine); OpenAI quota still gates live replays. Submission form is LIVE (fields captured; blog post + YouTube video are required).

## 2026-07-24 — P9 wave: full-product coherence (API + classes + integration) + remeasure ~64%

**Three composer worktree runs, driver-gated; opencode (grok/kimi) out on balance.**
P9-A — every route (33) audited vs docs/12 + tests + structured errors: 5 undocumented write/ops endpoints + agent-view replay route + griffin/evaluate now in docs/12 (doc-only, additive); model-intel 404 straggler moved to `{detail, hint}`; wrong curl in docs/26 fixed; `docs/28-api-coherence.md` audit table + 10 coherence tests. Driver fixed one test that mismodeled the signals contract (session queries include fleet-wide NULL rows by design — repository.list_signals scoping).
P9-B — every major class/module audited (`docs/29-class-audit.md`): dead `_action_name` removed; **real gap fixed** — ReplayCursor now surfaces recorded guard verdicts when no live runtime; griffin BUS.publish failures logged instead of swallowed; init() docstring corrected; sdk pricing vs model_catalog alignment test added. Flagged (deferred, honest): steer-guidance string duplication, anthropic pricing id namespace drift, HITL live relay.
P9-C — `scripts/e2e_product_coherence.py`: offline integration proof (seed sanity, link-driven agent-view graph walk, model-intel hand-recomputed + apply loop, verdict roundtrip into twins + case-file zip, HITL + BUS) — PASS on merged main; referenced from docs/14 as the product self-check.
**Remeasure (driver): ~62 → ~64 (cap ≤65)** citing P8 exits (docs/20 P8 table); README (was stale at ~57/≤60), docs/21/22/23/14/17, HQ home strip, and agent_home_data honesty all synced.
**Final gate on main:** server **159** / agents 17 / sdk **11** / hq 40 · boundaries clean · coherence script PASS. Services restarted on new code.

## 2026-07-24 — P10 wave: TabFM shipped + live-verified, flags closed, live checks ALL PASS

**Live checks (funded OpenAI key):** G4 hero re-verify PASS (Edgar + Worms 3/3 stable `mixed`, fresh `docs/_phase4_g4.json`); live S1/S2/S5 PASS (S1 `s_352fb834`, S2 `s_2458eb25`, S5 `s_ac9f30b3`) with P8-D verdict metadata proven end-to-end on real runs — coverage-matrix live-rerun DEFER closed.
**P7-B TabFM (composer, driver-gated + driver live-verified):** opt-in `ARCNET_TABFM=1` async daemon worker (N=1 series @ 360s per the P7-A decision), lazy weight load, permanent MAD degrade on any failure, `griffin/status` additive `tabfm{}` + truth-only `estimator`; subprocess test proves tabfm never imports when disabled. **Live verify:** one real cycle 123.7s (CPU, cached weights), estimator flipped `tabfm`, no degrade — `docs/_phase7_p7b_live.json`. Demo/default runtime stays MAD.
**P10-B flags closed (composer):** `BLOCK_STEER_GUIDANCE` extracted to guard_factory (both hot paths, byte-identical, tested); anthropic catalog-id → dated-slug aliases in sdk pricing with full cross-check test; `build_fleet_clone(role)` wired to Agno Agent.role; cosmetic read_models fix. Remaining honest flags: sources SSE (by design), HITL live relay (deferred).
**Submission kit (driver):** `docs/plans/video-script.md` (shot-by-shot, new surfaces in Beat 4), `docs/plans/blog-draft.md` (SigNoz implementation post, ready to publish), `docs/plans/submission-form-answers.md` (paste-ready). Form fields captured; blog + video remain the human deliverables.
**Final gate:** server **165** / agents **18** / sdk **14** / hq 40 · boundaries clean · coherence PASS · services restarted; all pushed.
