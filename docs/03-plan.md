# ArcNet — Build Plan v2 (phase-gated, sooner the better)

Solo build toward one hard date: **submission Sun Jul 26** (confirm the exact time from the form in Phase 0). Work is organized as **milestone-gated phases, not calendar days** — a phase starts the moment the previous exit is green, never on a date. Finish early, start the next; every hour banked flows into Phase 5–6 polish and re-records, which is where "breathtaking" actually comes from. Ceiling pace: all six phases must fit before the deadline (~a phase a day with the last two protected). Concept: `08-vision-v2.md` · Product: `01-product.md` · Specs: `10-time-machine.md` (headline) + `11-scenarios.md` (Bug Suite).

## The bar (the judge test)

Everything below serves one sentence: **"one person built this during the event — and it feels like a product."** Concretely:

- **Every phase exits demoable** — at any exit you could screen-record something real that minute.
- **The two hero views** (Fleet Health, Time Machine) get product polish: real data, zero empty states, zero debug text, the Unplug design language executed per `09-frontend.md`.
- **Nothing on camera depends on luck**: one-command bring-up, deterministic choreography, backups for every hard beat, rehearsed script.
- **Depth visible, not claimed**: dashboards/alerts provisioned as code, MCP live in the demo, precise verdicts with honest `inconclusive` paths.
- North star + success criteria + tradeoff order: `08-vision-v2.md`.

## Priority tiers (the demo defines P0)

**Anything the demo shows is P0.** The v2 demo has six beats; each maps to a P0 feature. The cut list holds only what no beat needs.

- **P0 — must land:** F1 instrumented fleet · F2 source-trust guard telemetry · F3 scenarios S0/S1/S2/S4/S5 · F4 SigNoz depth (dashboards, alerts, webhook) · F5 signals (steer/kill) · F6 Fleet Health view · F7 agent-view + Case File + MCP handoff · **F14 Time Machine (counterfactual replay)** · F13 Griffin core.
- **P1 — strong, build if P0 done:** native seasonal anomaly alert · Griffin breadth · Sources & Trust view · HITL pause beat · Time Machine corpus replay · prompt-swap replay · F9 canaries · **live-work agent on the fleet** (a real Agno agent doing genuine tasks under ArcNet — dogfood; makes the cold-open fleet honest) · context inspector (deferred by choice).
- **P2 — cut freely:** F10 LLM judge · F11 second adapter · Agent K persona · S3 Serleena.

**Honest scope note:** v2 is ambitious for a solo build — the Time Machine and a product-grade UI are both new since v1. The plan front-loads the two riskiest things (replay spike in Phase 0, TabFM spike in Phase 2) and the cut list protects the two hero views; everything else degrades to agent-view JSON or SigNoz deep-links.

## Phase 0 — Foundations & de-risk (timeboxed: one focused day — it de-risks everything else)

- [ ] **Two 10-minute checks before any code:** (a) confirm **both** provider keys (baseline + candidate model) exist and are funded for repeated 3-run replays; record which: ____ (b) chase the submission form + exact deadline time in the SigNoz Slack; record: ____
- [ ] **Post the unplug-ai provenance disclosure in the SigNoz Slack** (same text as the README) and ask for an explicit organizer ruling in writing; record the answer: ____
- [ ] Scaffold repo (layout per `02`), uv workspaces + pnpm app, `.env.example` fully enumerated
- [ ] SigNoz self-hosted via Docker Compose; pin version; confirm UI; note Mac resource usage
- [ ] Hello Agno agent traced into SigNoz via `openinference-instrumentation-agno==0.1.38`; pin `agno==2.7.4`; import prebuilt Agno dashboard
- [ ] **Pull one live trace and record the REAL span names + attribute keys** (OpenInference semconv — `{agent}.run`/`{model}.invoke`/`{tool}`, `llm.token_count.*` — NOT `gen_ai.*`) → paste into `04` before any dashboard/alert JSON is authored
- [ ] Verify Agno hook surface on the pinned version: guardrail base class (input-only), per-tool pre/post hooks, agent-level `tool_hooks` middleware, `post_hooks`, HITL, `cancel_run` — record exact signatures in `02`
- [ ] `pip install unplug-ai==0.5.2` → **first smoke test = the exact S1 taint chain** (scan retrieved text → `notify_taint_source` → `check_tool_call` blocks `send_email`) — the highest-consequence assumption in the plan; then the rest of the `05` API list
- [ ] **Replay feasibility spike (≤2h):** intercept an Agno agent's tool calls, return canned outputs, confirm the step-cursor mechanism + transcript shape per `10-time-machine.md`; **in the same spike, test steer propagation** (state written inside tool call N visible to the model at call N+1? if not → per-call substitution fallback, `02` §3)
- [ ] **Oversized-fixture check:** push one deliberately large page through the pipeline; find the span-attribute truncation point (transcripts are SQLite-primary regardless — `10`)
- [ ] Model pick + confirm token/cost path + write `pricing.py`
- [ ] Service-account key — check whether it can be created headlessly; if not, document the one manual UI step honestly in the README. One Query Range call working.

**Exit: hello-Agno trace with tokens visible in SigNoz (real attribute names recorded in `04`); S1 taint chain proven in unplug; replay + steer mechanisms proven on a toy agent; both model keys confirmed; organizer ruling requested.**

## Phase 1 — Shield Core (source-trust)

- [ ] `arcnet.init()` — OTel providers + `AgnoInstrumentor` + Guard + stub signal client
- [ ] `UnplugGuardrail` + tool hooks: 4 checkpoints emitting `arcnet.guard` spans (with trust level), events per finding, metrics, logs; `block` → span ERROR; `arcnet.exposure` per agent
- [ ] Agent J on AgentOS + 4 tools + seeded PII + fixture pages (`11-scenarios.md`); **record replay-ready transcripts** on every session (SQLite-primary + span summaries per `10`) so the Time Machine can reload them
- [ ] Scenario runner (with per-scenario assertions per `11`) + S0 baseline + S5 jailbreak block
- [ ] Custom metrics: `arcnet.threats.detected`, `arcnet.guard.latency`, token/cost rollups

**Exit: S5 → blocked span + metric; S0 → clean run; a recorded session round-trips through the replay loader.**

## Phase 2 — SigNoz Depth + MCP

- [ ] **TabFM spike — FIRST item of the phase, 45–90 min walk-away** (zero public CPU benchmarks exist; most of the budget will be install friction): install from git, backend choice, M-series latency; fall to `tabpfn==8.1.0` fast (gate G2)
- [ ] S2 Neuralyzer (output redact)
- [ ] Dashboards ×3 imported via script: Fleet Ops, Threats & Trust, Cost & Tokens (≥1 ClickHouse-SQL panel) — authored against the **real OpenInference attribute names recorded in Phase 0**
- [ ] Alert rules: threat>0, cost burn, tool-calls/session, p99 latency, error rate, `arcnet.anomaly>0` — **payloads in the current v5 `queries` format** (legacy `builderQueries` is rejected on modern SigNoz; crib from the Terraform-provider examples); record the eval interval + tune `for:` windows (on-camera steer rides the inline fast-path per `02` §3)
- [ ] Native SigNoz seasonal anomaly alert on ≥1 metric — **screenshot-only artifact** (its eval windows are ≥5m by design; it can never fire live on camera; the pairing story is a configured-rule + pre-seeded-history visual)
- [ ] Webhook channel → server skeleton (SQLite); alert labels carry `session_id`/`agent_id`
- [ ] Logs correlated by trace_id
- [ ] SigNoz MCP server (`v0.8.0`) self-hosted + wired into Cursor/Claude Code; agent-skills plugin installed
- [ ] **Integration seam check (end of phase):** one stub `hq/` page → `server/` → SigNoz end-to-end (CORS, SSE reconnect, ports) — surface the seam bugs before any UI polish depends on them

**Exit: S5 → alert fires → webhook lands attributable; S2 → redacted finding; Griffin model locked; MCP answering IDE queries; the UI↔server↔SigNoz seam works once.**

## Phase 3 — Signals + Griffin

- [ ] Signal bus: `Signal{session_id, agent_id, kind, severity, reason, evidence_link, guidance}`; SSE; **inline fast-path** (`POST /api/signal` from the SDK at block time) + webhook-driven path
- [ ] SDK signal client + Agno steer/kill (pause HITL scaffold)
- [ ] S1 Edgar end-to-end (source-trust flags scraped page → block exfil → steer → self-correct); S4 Worms (kill) — rehearse the pair per `11`
- [ ] Griffin core: worker on token-rate series, conformal judge, `arcnet.anomaly` + alert rule; `seed.py`; S4 "Griffin-first" choreography
- [ ] **Parallel track (start here, land in Phase 5):** scaffold `hq/` shell + Time Machine & Fleet Health views against **mock data** — the verdict JSON in `10` is the frozen contract; UI work must not wait for the real replay endpoint
- [ ] **Gate G3 replay tripwire (exit):** bare-bones manual replay (no API, no UI) of the real S1 + S4 transcripts against the candidate model — the behavioral gap must show up NOW, not at Phase 4 exit

**Exit: S1 + S4 self-resolve at camera speed; Griffin flags S4 before the static alert; manual replay tripwire passed (gate G3); UI shells render on mock data.**

## Phase 4 — Time Machine (the headline)

- [ ] `arcnet/replay.py` — replay harness per `10-time-machine.md`: tool stubs with step cursor, divergence logging, temp 0, same guardrail
- [ ] `POST /api/replay` — load recorded session → replay vs candidate model → **trajectory diff** `{goal_reached, steps, tool_errors, cost, latency, tokens}` + security dims for threat sessions → verdict + recommendation (3-run majority)
- [ ] Verify **both hero replays**: Worms (baseline killed → candidate stops the loop) and Edgar (baseline exploited → candidate resists); **stable across 3 runs each** (gate G4)
- [ ] `GET /api/agent-view/replay/{id}` — machine-optimal JSON of the verdict

**Exit: `POST /api/replay` returns real, stable Worms + Edgar counterfactuals; agent-view JSON of them.**

## Phase 5 — UI + Case File + Record

- [ ] Finish the React app started in Phase 3's parallel track (direction: `09-frontend.md`): wire **Fleet Health** + **Time Machine** to real APIs; Signals + Case Files views
- [ ] **Global Human ⇄ Agent view toggle** wired to `/api/agent-view/*`
- [ ] Case File exporter (`case-file.md`+`.json`, embedded trace_ids + MCP instructions); "hand to coding agent" flow
- [ ] Live test: hand a Case File to Claude Code (SigNoz MCP connected) → it pulls traces + proposes the fix; **record a backup of this beat** (gate G5)
- [ ] Seed rich history for the dashboards; Neuralyzer redaction surfaced; `scripts/run-demo.sh`; polish empty/error states
- [ ] README rewrite incl. the **screenshot slots judges score**: all 3 dashboards, the ClickHouse-SQL panel with its query visible, the seasonal-anomaly rule next to Griffin's card (the pairing visual)
- [ ] **Video half-day (protected block):** assemble from the per-beat clips captured at each phase exit + narration + retakes — video production is a 3–5× underestimate when left as a trailing bullet
- [ ] **Pre-cut from the demo path:** the 12-incident corpus recording + aggregate — post-recording hours only; if it happens it's a README artifact, never an on-camera element

**Exit: end-to-end demo recorded (with backups); the two hero views product-polished. Any time left after this exit = polish loop: re-record weak beats, tighten the UI, add P1s (corpus first).**

## Phase 6 — Ship (the only calendar-bound phase: Sun Jul 26)

- [ ] Final video per `06`; README final (setup, screenshots, criteria map, env)
- [ ] Repo public, license, **submit hours before deadline**, social post
- [ ] Buffer

## Gates (pre-agreed decisions — don't relitigate mid-build)

| Gate | When | If red |
|---|---|---|
| G1 replay + steer spike | Phase 0 | Replay mechanism unproven → Time Machine scope narrows to single-scenario replay. Steer propagation dead → per-call substitution fallback (`02` §3) |
| G2 TabFM | first item of Phase 2, 45–90 min | Latency/API rough → `tabpfn==8.1.0` same hour, no revisit (`07`) |
| G3 replay tripwire | Phase 3 exit | Bare-bones manual replay of real S1+S4 transcripts: if baseline and candidate don't diverge cleanly, switch model pair / scenario variant **now** — discovering it at Phase 4 exit leaves no room to react |
| G4 hero-replay stability (Worms + Edgar) | Phase 4 exit | 3 runs disagree → switch candidate model or scenario variant with a larger gap; if only one replay is stable, it carries the beat live and the other uses the Phase 5 backup capture |
| G5 MCP handoff | Phase 5 | MCP flaky in the live test → Case File instructions use the Query Range API via curl; beat keeps working |

## Cut list (pull in this order when a phase overruns — cut, don't slip the chain)

1. F11 second adapter · F10 LLM judge
2. HITL pause beat (dev path stays, not on camera)
3. Time Machine corpus replay + prompt-swap — **already pre-cut from the demo path** (Phase 5); this rung just confirms it stays cut
4. Sources & Trust view → fold into Fleet Health + agent-view JSON
5. Griffin breadth (auto-discovery → hardcode 3 series; TabFM→TabPFN→MAD)
6. Signals view → SigNoz deep-link; keep the live threat feed only
7. Agent K persona · S3 Serleena — **note:** even fully cut, agents L & O (clones per `11-scenarios.md`) keep the fleet real; never demo a fleet of one

**Never cuttable:** Fleet Health view, Time Machine view, F14 replay logic, agent-view toggle, Griffin core, SigNoz MCP in the Case File beat. These carry demo beats.

## Standing rules

- Provision everything as code — judge runs `docker compose up` + `./scripts/run-demo.sh`.
- Every scenario emits telemetry even when blocked.
- **This repo outlives the hackathon**: demo scaffolding stays in `agents/`/`scripts/`; `sdk/`/`server/`/`hq/` never depend on scenario code (`02`).
- **Capture a 20–60s screen clip the moment any phase exits demoable** — the video assembles from clips, not from one Saturday marathon.
- **Timebox rule:** a phase >130% of its budget at its midpoint → invoke the cut list immediately; don't finish-then-cut.
- Scenario assertions are gating only for S1/S4/S5 (the on-camera three); advisory for the rest.
- **Check the submission form daily.**
- Commit small, messages describe WHAT shipped.
- End of each day AND each phase: 2-line note in `docs/log.md` — which phase, expected vs actual. Phase-gating is not license to lose the calendar.
