# ArcNet — Build Plan v2 (re-anchored: build Tue Jul 21 – Sat Jul 25, ship Sun Jul 26)

Solo build. **Mon Jul 20 went to concept + planning (v1→v2 pivot — worth it; see `docs/log.md`), so the build window is 5 days: Tue 21 · Wed 22 · Thu 23 · Fri 24 · Sat 25, with Sun Jul 26 = ship + submit** (confirm exact deadline time from the form Day 1). The compression is absorbed by making Tue a double day (foundations AM + shield core PM) and pushing two items to Wed (TabFM spike, S2). Concept: `08-vision-v2.md` · Product: `01-product.md` · Specs: `10-time-machine.md` (headline) + `11-scenarios.md` (Bug Suite).

## Priority tiers (the demo defines P0)

**Anything the demo shows is P0.** The v2 demo has six beats; each maps to a P0 feature. The cut list holds only what no beat needs.

- **P0 — must land:** F1 instrumented fleet · F2 source-trust guard telemetry · F3 scenarios S0/S1/S2/S4/S5 · F4 SigNoz depth (dashboards, alerts, webhook) · F5 signals (steer/kill) · F6 Fleet Health view · F7 agent-view + Case File + MCP handoff · **F14 Time Machine (counterfactual replay)** · F13 Griffin core.
- **P1 — strong, build if P0 done:** native seasonal anomaly alert · Griffin breadth · Sources & Trust view · HITL pause beat · Time Machine corpus replay · prompt-swap replay · F9 canaries.
- **P2 — cut freely:** F10 LLM judge · F11 second adapter · Agent K persona · S3 Serleena.

**Honest scope note:** v2 is ambitious for solo/5-build-days — the Time Machine and a product-grade UI rebuild are both new since v1. The plan front-loads the two riskiest new things (replay harness Tue, TabFM Wed) and the cut list protects the two hero UI views (Fleet Health + Time Machine); everything else degrades to agent-view JSON or SigNoz deep-links.

## Day 1 — Tue Jul 21 · Foundations (AM) + Shield Core (PM)

**AM — foundations & de-risk (timeboxed, ~5h):**
- [ ] Scaffold repo (layout per `02`), uv workspaces + pnpm app, `.env.example` fully enumerated
- [ ] SigNoz self-hosted via Docker Compose; pin version; confirm UI; note Mac resource usage
- [ ] Join SigNoz Slack + register; **find submission form + exact deadline time; record:** ____
- [ ] Hello Agno agent traced into SigNoz via `openinference-instrumentation-agno==0.1.38`; pin `agno==2.7.4`; import prebuilt Agno dashboard
- [ ] Verify Agno hook surface on the pinned version: guardrail base class, tool pre/post hooks, HITL, `cancel_run` — record exact APIs in `02`
- [ ] `pip install unplug-ai==0.5.2` → smoke test; verify the day-0 API list (`add_canary`, `notify_taint_source`, `wrap_for_context`, trust levels) per `05`
- [ ] **Replay feasibility spike (≤2h):** intercept an Agno agent's tool calls, return canned outputs, confirm the step-cursor mechanism + recorded-transcript shape per `10-time-machine.md`. De-risks the F14 headline 3 days early.
- [ ] Model pick (gpt-4o-mini vs haiku by keys) + confirm token/cost path + write `pricing.py`
- [ ] Service-account key; one Query Range call + confirm a metrics-listing path (Griffin discover)

**PM — shield core (source-trust):**
- [ ] `arcnet.init()` — OTel providers + `AgnoInstrumentor` + Guard + stub signal client
- [ ] `UnplugGuardrail` + tool hooks: 4 checkpoints emitting `arcnet.guard` spans (with trust level), events per finding, metrics, logs; `block` → span ERROR; `arcnet.exposure` per agent
- [ ] Agent J on AgentOS + 4 tools + seeded PII + fixture pages (`11-scenarios.md`); **record replay-ready transcripts** on every session (dual-write per `10`) so the Time Machine can reload them
- [ ] Scenario runner (with per-scenario assertions per `11`) + S0 baseline + S5 jailbreak block
- [ ] Custom metrics: `arcnet.threats.detected`, `arcnet.guard.latency`, token/cost rollups

**Exit: Agno trace with tokens in SigNoz; replay mechanism proven on a toy agent; demo model locked; S5 → blocked span + metric; S0 → clean run; a recorded session round-trips through the replay loader.**

## Day 2 — Wed Jul 22 · SigNoz Depth + MCP

- [ ] S2 Neuralyzer (output redact) — carried from Day 1
- [ ] **TabFM spike (≤2h):** install from git, backend choice, M-series latency; lock TabFM vs `tabpfn==8.1.0` before Griffin core tomorrow
- [ ] Dashboards ×3 imported via script: Fleet Ops, Threats & Trust, Cost & Tokens (≥1 ClickHouse-SQL panel)
- [ ] Alert rules: threat>0, cost burn, tool-calls/session, p99 latency, error rate, `arcnet.anomaly>0`; **record the alert evaluation interval and tune eval/`for:` windows for demo latency** (the on-camera steer uses the inline fast-path per `02` §3 — the alert is the system of record)
- [ ] Native SigNoz seasonal anomaly alert on ≥1 metric (Griffin pairing story)
- [ ] Webhook channel → server skeleton (SQLite); alert labels carry `session_id`/`agent_id`
- [ ] Logs correlated by trace_id
- [ ] SigNoz MCP server (`v0.8.0`) self-hosted + wired into Cursor/Claude Code; agent-skills plugin installed

**Exit: S5 → alert fires → webhook lands attributable; S2 → redacted finding; Griffin model locked; MCP answering IDE queries.**

## Day 3 — Thu Jul 23 · Signals + Griffin

- [ ] Signal bus: `Signal{session_id, agent_id, kind, severity, reason, evidence_link, guidance}`; SSE; **inline fast-path** (`POST /api/signal` from the SDK at block time) + webhook-driven path
- [ ] SDK signal client + Agno steer/kill (pause HITL scaffold)
- [ ] S1 Edgar end-to-end (source-trust flags scraped page → block exfil → steer → self-correct); S4 Worms (kill) — rehearse the pair per `11`
- [ ] Griffin core: worker on token-rate series, conformal judge, `arcnet.anomaly` + alert rule; `seed.py`; S4 "Griffin-first" choreography

**Exit: S1 + S4 self-resolve on camera-speed; Griffin flags S4 before the static alert; replay-loader source locked (gate G3).**

## Day 4 — Fri Jul 24 · Time Machine (the headline)

- [ ] `arcnet/replay.py` — replay harness per `10-time-machine.md`: tool stubs with step cursor, divergence logging, temp 0, same guardrail
- [ ] `POST /api/replay` — load recorded session → replay vs candidate model → **trajectory diff** `{resisted_injection, exfil_attempts, goal_reached, cost, latency}` → verdict + recommendation (3-run majority)
- [ ] Verify the Edgar replay: baseline (exploited) vs candidate → candidate resists; **stable across 3 runs**
- [ ] `GET /api/agent-view/replay/{id}` — machine-optimal JSON of the verdict

**Exit: `POST /api/replay` returns a real, stable Edgar counterfactual; agent-view JSON of it.**

## Day 5 — Sat Jul 25 · UI + Case File + Record

- [ ] Product-grade React app (direction: `09-frontend.md`; Unplug-matched aesthetic): shell + **Fleet Health** + **Time Machine** (the two hero views) + Signals + Case Files
- [ ] **Global Human ⇄ Agent view toggle** wired to `/api/agent-view/*`
- [ ] Case File exporter (`case-file.md`+`.json`, embedded trace_ids + MCP instructions); "hand to coding agent" flow
- [ ] Live test: hand a Case File to Claude Code (SigNoz MCP connected) → it pulls traces + proposes the fix; **record a backup of this beat**
- [ ] Seed rich history + **record the 12-incident replay corpus** (`11-scenarios.md`); (P1) corpus replay aggregate; (P1) Sources & Trust view
- [ ] Neuralyzer redaction surfaced; `scripts/run-demo.sh`; polish empty/error states; README rewrite
- [ ] **Record demo video draft** (<3 min) + per-beat backup captures

**Exit: end-to-end demo recorded (with backups); the two hero views solid.**

## Day 6 — Sun Jul 26 · Ship

- [ ] Final video per `06`; README final (setup, screenshots, criteria map, env)
- [ ] Repo public, license, **submit hours before deadline**, social post
- [ ] Buffer

## Gates (pre-agreed decisions — don't relitigate mid-build)

| Gate | When | If red |
|---|---|---|
| G1 replay spike | Tue AM | Mechanism unproven → transcripts become the SQLite-only design immediately; Time Machine scope narrows to single-scenario replay |
| G2 TabFM | Wed | Latency/API rough → `tabpfn==8.1.0` same-day, no revisit (`07`) |
| G3 replay-loader source | Thu EOD | Query Range round-trip flaky → SQLite loader is the demo path; SigNoz stays proof store + deep-links (`10`) |
| G4 Edgar replay stability | Fri EOD | 3 runs disagree → switch candidate model or scenario variant with a larger gap; if still unstable, demo uses Sat's backup capture and the live take is dropped |
| G5 MCP handoff | Sat | MCP flaky in the live test → Case File instructions use the Query Range API via curl; beat keeps working |

## Cut list (pull in this order when behind)

1. F11 second adapter · F10 LLM judge
2. HITL pause beat (dev path stays, not on camera)
3. Time Machine corpus replay + prompt-swap (single-incident replay is the demo; corpus is the "scales to" line)
4. Sources & Trust view → fold into Fleet Health + agent-view JSON
5. Griffin breadth (auto-discovery → hardcode 3 series; TabFM→TabPFN→MAD)
6. Signals view → SigNoz deep-link; keep the live threat feed only
7. Agent K persona · S3 Serleena — **note:** even fully cut, agents L & O (clones per `11-scenarios.md`) keep the fleet real; never demo a fleet of one

**Never cuttable:** Fleet Health view, Time Machine view, F14 replay logic, agent-view toggle, Griffin core, SigNoz MCP in the Case File beat. These carry demo beats.

## Standing rules

- Provision everything as code — judge runs `docker compose up` + `./scripts/run-demo.sh`.
- Every scenario emits telemetry even when blocked.
- **Check the submission form daily.**
- Commit small, messages describe WHAT shipped.
- End of day: 2-line note in `docs/log.md`.
