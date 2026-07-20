# ArcNet — Build Plan v2 (Mon Jul 20 – Sun Jul 26 2026)

Solo build, 7 days. **Calendar (verified):** Mon 20 · Tue 21 · Wed 22 · Thu 23 · Fri 24 · Sat 25 · Sun 26. Build Mon–Sat; **Sun Jul 26 = ship + submit** (confirm exact deadline time from the form Day 0). Concept: `08-vision-v2.md`. Product: `01-product.md`.

## Priority tiers (the demo defines P0)

**Anything the demo shows is P0.** The v2 demo has six beats; each maps to a P0 feature. The cut list holds only what no beat needs.

- **P0 — must land:** F1 instrumented fleet · F2 source-trust guard telemetry · F3 scenarios S0/S1/S2/S4/S5 · F4 SigNoz depth (dashboards, alerts, webhook) · F5 signals (steer/kill) · F6 Fleet Health view · F7 agent-view + Case File + MCP handoff · **F14 Time Machine (counterfactual replay)** · F13 Griffin core.
- **P1 — strong, build if P0 done:** native seasonal anomaly alert · Griffin breadth · Sources & Trust view · HITL pause beat · Time Machine corpus replay · F9 canaries.
- **P2 — cut freely:** F10 LLM judge · F11 second adapter · Agent K · S3 Serleena.

**Honest scope note:** v2 is ambitious for solo/6-day — the Time Machine and a product-grade UI rebuild are both new since v1. The plan front-loads the two riskiest new things (replay harness, TabFM) and the cut list protects the two hero UI views (Fleet Health + Time Machine); everything else degrades to agent-view JSON or SigNoz deep-links.

## Phase 0 — Mon Jul 20 · Foundations & de-risk

- [ ] Scaffold repo (layout per `02`), uv workspaces + pnpm app, `.env.example` fully enumerated
- [ ] SigNoz self-hosted via Docker Compose; pin version; confirm UI; note Mac resource usage
- [ ] Join SigNoz Slack + register; **find submission form + exact deadline time; record:** ____
- [ ] Hello Agno agent traced into SigNoz via `openinference-instrumentation-agno==0.1.38`; pin `agno==2.7.4`; import prebuilt Agno dashboard
- [ ] Verify Agno hook surface on the pinned version: guardrail base class, tool pre/post hooks, HITL, `cancel_run` — record exact APIs in `02`
- [ ] `pip install unplug-ai==0.5.2` → smoke test; verify the day-0 API list (`add_canary`, `notify_taint_source`, `wrap_for_context`, trust levels) per `05`
- [ ] **Replay feasibility spike (≤2h):** can we run an Agno agent while intercepting its tool calls to return canned outputs? Confirm the mechanism (tool wrapper / hook) and what to record per step (goal, tool I/O, model turn). This de-risks the F14 headline 4 days early.
- [ ] **TabFM spike (≤2h):** install from git, backend choice, M-series latency; lock TabFM vs `tabpfn==8.1.0`
- [ ] Model pick (gpt-4o-mini vs haiku by keys) + confirm token/cost path + write `pricing.py`
- [ ] Service-account key; one Query Range call + confirm a metrics-listing path (Griffin discover)

**Exit: Agno trace with tokens in SigNoz; replay mechanism proven on a toy agent; Griffin model + demo model locked; Query API working.**

## Phase 1 — Tue Jul 21 · Shield Core (source-trust)

- [ ] `arcnet.init()` — OTel providers + `AgnoInstrumentor` + Guard + stub signal client
- [ ] `UnplugGuardrail` + tool hooks: 4 checkpoints emitting `arcnet.guard` spans (with trust level), events per finding, metrics, logs; `block` → span ERROR; `arcnet.exposure` per agent
- [ ] Agent J on AgentOS + 4 tools + seeded PII + fixture pages; **record replay-ready attributes** on every step (goal, tool I/O, model turn) so the Time Machine can reload sessions
- [ ] Scenario runner + S0 baseline, S5 jailbreak block, S2 PII redact
- [ ] Custom metrics: `arcnet.threats.detected`, `arcnet.guard.latency`, token/cost rollups

**Exit: S5 → blocked span + metric; S2 → redacted finding; S0 → clean run; a recorded session round-trips through the replay loader.**

## Phase 2 — Wed Jul 22 · SigNoz Depth + MCP

- [ ] Dashboards ×3 imported via script: Fleet Ops, Threats & Trust, Cost & Tokens (≥1 ClickHouse-SQL panel)
- [ ] Alert rules: threat>0, cost burn, tool-calls/session, p99 latency, error rate, `arcnet.anomaly>0`
- [ ] Native SigNoz seasonal anomaly alert on ≥1 metric (Griffin pairing story)
- [ ] Webhook channel → server skeleton (SQLite); alert labels carry `session_id`/`agent_id`
- [ ] Logs correlated by trace_id
- [ ] SigNoz MCP server (`v0.8.0`) self-hosted + wired into Cursor/Claude Code; agent-skills plugin installed

**Exit: S5 → alert fires → webhook lands attributable; MCP answering IDE queries.**

## Phase 3 — Thu Jul 23 · Signals + Griffin

- [ ] Signal bus: `Signal{session_id, agent_id, kind, severity, reason, evidence_link, guidance}`; SSE
- [ ] SDK signal client + Agno steer/kill (pause HITL scaffold)
- [ ] S1 Edgar end-to-end (source-trust flags scraped page → block exfil → steer → self-correct); S4 Worms (kill)
- [ ] Griffin core: worker on token-rate series, conformal judge, `arcnet.anomaly` + alert rule; `seed.py`; S4 "Griffin-first" choreography

**Exit: S1 + S4 self-resolve; Griffin flags S4 before the static alert.**

## Phase 4 — Fri Jul 24 · Time Machine (the headline)

- [ ] `arcnet/replay.py` — replay harness: run an Agno agent against a recorded session with tool outputs mocked, temp 0
- [ ] `POST /api/replay` — load recorded session (SigNoz/SQLite) → replay vs candidate model → **trajectory diff** `{resisted_injection, exfil_attempts, goal_reached, cost, latency}` → verdict + recommendation
- [ ] Verify the Edgar replay: baseline (gpt-4o-mini, exploited) vs candidate → candidate resists; stable across 3 runs
- [ ] `GET /api/agent-view/replay/{id}` — machine-optimal JSON of the verdict

**Exit: `POST /api/replay` returns a real, stable Edgar counterfactual; agent-view JSON of it.**

## Phase 5 — Sat Jul 25 · UI + Case File + Record

- [ ] Product-grade React app (direction: `09-frontend.md`; Unplug-matched aesthetic): shell + **Fleet Health** + **Time Machine** (the two hero views) + Signals + Case Files
- [ ] **Global Human ⇄ Agent view toggle** wired to `/api/agent-view/*`
- [ ] Case File exporter (`case-file.md`+`.json`, embedded trace_ids + MCP instructions); "hand to coding agent" flow
- [ ] Live test: hand a Case File to Claude Code (SigNoz MCP connected) → it pulls traces + proposes the fix; **record a backup of this beat**
- [ ] Neuralyzer redaction surfaced; (P1) Sources & Trust view
- [ ] `scripts/run-demo.sh` + seed rich history; polish empty/error states; README rewrite
- [ ] **Record demo video draft** (<3 min) + per-beat backup captures

**Exit: end-to-end demo recorded (with backups); the two hero views solid.**

## Phase 6 — Sun Jul 26 · Ship

- [ ] Final video per `06`; README final (setup, screenshots, criteria map, env)
- [ ] Repo public, license, **submit hours before deadline**, social post
- [ ] Buffer

## Cut list (pull in this order when behind)

1. F11 second adapter · F10 LLM judge
2. HITL pause beat (dev path stays, not on camera)
3. Time Machine corpus replay (single-incident replay is the demo; corpus is the "scales to" line)
4. Sources & Trust view → fold into Fleet Health + agent-view JSON
5. Griffin breadth (auto-discovery → hardcode 3 series; TabFM→TabPFN→MAD)
6. Signals view → SigNoz deep-link; keep the live threat feed only
7. Agent K · S3 Serleena

**Never cuttable:** Fleet Health view, Time Machine view, F14 replay logic, agent-view toggle, Griffin core, SigNoz MCP in the Case File beat. These carry demo beats.

## Standing rules

- Provision everything as code — judge runs `docker compose up` + `./scripts/run-demo.sh`.
- Every scenario emits telemetry even when blocked.
- **Check the submission form daily.**
- Commit small, messages describe WHAT shipped.
- End of day: 2-line note in `docs/log.md`.
