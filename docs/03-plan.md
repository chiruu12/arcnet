# ArcNet — Build Plan (Mon Jul 20 – Sun Jul 26 2026)

Solo build, 7 days. **Calendar (verified):** Mon 20 · Tue 21 · Wed 22 · Thu 23 · Fri 24 · Sat 25 · Sun 26. Build Mon–Sat; **Sun Jul 26 is ship + submit day** — the event runs through Jul 26, so treat Sun as the hard deadline and confirm the exact submission time from the form on Day 1.

## Priority tiers (the demo defines P0)

The old plan let the demo depend on "P1/cuttable" features. Fixed: **anything the demo shows is P0.** Cut list contains only things no beat needs.

- **P0 — demo-critical, must land:** F1 fleet telemetry · F2 guard telemetry · F3 Bug Suite (S0/S1/S2/S4/S5) · F4 SigNoz depth (dashboards, alerts, webhook) · F5 signals (steer + kill) · F6 HQ core (fleet board, threat feed, signals log, Griffin card) · F7 Case File + MCP handoff · F8 Neuralyzer · **F13 Griffin core** (single-series anomaly).
- **P1 — strong, build if P0 done:** native SigNoz seasonal anomaly alert · Griffin breadth (auto-discovery, top-N) · F9 canaries · HITL pause beat · HQ Session Detail.
- **P2 — cut freely:** F10 LLM judge · F11 second framework adapter · Agent K · S3 Serleena.

Rule: **no P1 work starts until all P0 lands.** (F12 was the standalone SigNoz-MCP feature — folded into F7, so numbering skips it.)

## Phase 0 — Mon Jul 20 · Foundations & de-risk

Retire every scary unknown today; get telemetry flowing end-to-end.

- [ ] Scaffold repo (layout per `02-architecture.md`), uv workspaces + pnpm app, **`.env.example` fully enumerated** (see `02` Secrets & env)
- [ ] SigNoz self-hosted via Docker Compose; pin version; confirm UI; note resource usage on the Mac
- [ ] Join SigNoz Slack + register for hackathon; **find the submission form + exact deadline time; record here:** ____
- [ ] Hello-world **Agno** agent traced into SigNoz via `openinference-instrumentation-agno==0.1.38` (guide: https://signoz.io/docs/agno-monitoring/); pin `agno==2.7.4`
- [ ] Import prebuilt **Agno dashboard template**
- [ ] Verify Agno hook surface on the pinned version: guardrail base class, tool pre/post hooks, HITL pause/resume, run cancellation — record exact APIs in `02-architecture.md`
- [ ] `pip install unplug-ai==0.5.2` → smoke test `Guard().scan()`; **verify the day-1 API list** (`add_canary`, `notify_taint_source`, `wrap_for_context`, `metrics`) per `05`; adjust `05` where drifted
- [ ] Confirm token metrics path (Agno per-run metrics → OTel counters) **and write the model price constants** for `arcnet.cost.usd` (see `04`)
- [ ] SigNoz service-account API key; one Query Range call **and confirm a metrics-listing endpoint exists** (Griffin's Discover step depends on it — `07`)
- [ ] **Timeboxed TabFM spike (≤2h):** install `tabfm` from git (JAX vs PyTorch backend), measure fit+predict latency on M-series for ~200×10; **decide TabFM vs `tabpfn==8.1.0` now** and record. This de-risks the headline model 3 days before Griffin core.

**Exit: an Agno trace with LLM + tool spans and token counts in SigNoz; Query API + metrics-list working; the Griffin model choice locked.**

## Phase 1 — Tue Jul 21 · Shield Core

Threats become first-class telemetry.

- [ ] `arcnet.init()` — OTel providers + `AgnoInstrumentor` + Guard + (stub) signal client
- [ ] `UnplugGuardrail` + tool hooks: 4 checkpoints (input / retrieved / tool-call / output) → `arcnet.guard` spans, per-finding events, metrics, logs; `block` → span ERROR
- [ ] Agent J on AgentOS with the 4 tools + seeded PII "database" + fixture web pages
- [ ] Scenario runner CLI + **S0 baseline**, **S5 jailbreak block**, **S2 PII redact**
- [ ] Custom metrics live: `arcnet.threats.detected`, `arcnet.guard.latency`, token/cost rollups

**Exit: S5 → blocked span + threat metric in SigNoz; S2 → redacted output + finding event; S0 → clean run.**

## Phase 2 — Wed Jul 22 · SigNoz Depth + MCP

Max "Best Use of SigNoz"; provision-as-code.

- [ ] Dashboards ×3 imported via script: Fleet Ops, Threats & Security, Cost & Tokens (≥1 ClickHouse-SQL panel)
- [ ] Alert rules provisioned: threat>0 (1m), cost burn, tool-calls/session (loop), p99 latency, error rate, `arcnet.anomaly>0`
- [ ] **Native SigNoz seasonal anomaly alert** on ≥1 metric (the pairing story with Griffin — `07`, `04`)
- [ ] Webhook channel → `server/webhooks/signoz`; FastAPI skeleton receiving + storing (SQLite); **alert labels carry `session_id`/`agent_id`** for attribution
- [ ] Structured logs correlated by trace_id
- [ ] **SigNoz MCP server** (`v0.8.0`) self-hosted + wired into Cursor/Claude Code; SigNoz **agent-skills** plugin installed — use both from here on

**Exit: S5 → SigNoz alert fires → webhook lands in server DB, attributable to the session; MCP answering queries from the IDE.**

## Phase 3 — Thu Jul 23 · Signals Loop + Griffin core

The headline, plus the anomaly precog.

- [ ] Signal bus: alert → `Signal{session_id, agent_id, kind, severity, reason, evidence_link, guidance}`; SSE (per-session + firehose)
- [ ] SDK signal client + Agno integration inside tool hooks: **steer** (inject guidance, continue) / **kill** (cancel_run) / pause (HITL scaffold)
- [ ] **S1 Edgar** end-to-end: poisoned page → taint → blocked exfil → alert → steer → self-correct
- [ ] **S4 The Worms**: loop burn → cost/loop alert → kill
- [ ] **Griffin core** (model chosen Day 0): worker on the token-rate series, conformal judge, `arcnet.anomaly` emission + alert rule
- [ ] **`scripts/seed.py` built here** (Griffin needs warm history to be testable same-day — was Phase 5)
- [ ] **S4 choreography:** demo-mode Griffin runs on a short cadence (or on-demand eval at scenario launch) and the static cost-burn alert uses a longer `for` window, so Griffin provably fires **first** (see `07` + `06`)

**Exit: S1 + S4 self-resolve unattended; Griffin flags S4's token spike before the static alert, on warm seeded data.**

## Phase 4 — Fri Jul 24 · HQ Dashboard

The MIB observation deck (P0 core).

- [ ] Vite + Tailwind app, MIB visual pass (per `01` visual language; the mock in `docs/mock/hq.html` is the reference)
- [ ] Fleet Board (registry + live status) · Threat Feed (SSE) · Signals Log · **Griffin card** (sparkline + forecast band + observed dot)
- [ ] Neuralyzer flash on redaction events; before/after view
- [ ] Server proxies for `/api/fleet`, `/api/threats`, `/api/sessions/{id}`; deep-links into SigNoz UI

**Exit: full Bug Suite drivable while HQ + SigNoz tell the story live.**

## Phase 5 — Sat Jul 25 · Case File + Record

- [ ] Case File exporter: Query API → `case-file.md` (timeline, findings, evidence, fix-prompt, embedded trace_ids + MCP instructions) + JSON; HQ export button
- [ ] **Record a safe backup of Beat 4 early** (pre-captured Cursor+MCP investigation), then attempt the live take — the live coding-agent+MCP beat is a bonus, not a gamble
- [ ] P1 if on schedule: Griffin breadth (auto-discovery, top-N), canary registration (F9), HQ Session Detail, HITL pause beat
- [ ] `scripts/run-demo.sh` one-command bring-up + seed rich history for a full-looking board
- [ ] Polish: empty states, demo-path error handling, README rewrite with architecture diagram + screenshots
- [ ] **Record demo video draft** (<3 min) + per-beat backup captures

**Exit: end-to-end demo recorded (with backups); repo demo-ready.**

## Phase 6 — Sun Jul 26 · Ship (deadline day)

- [ ] Final video + narration per `06-demo-script.md`
- [ ] README final: setup, screenshots, judging-criteria map, env surface
- [ ] Repo public, license, **submit hours before the deadline time confirmed on Day 0**, social post (side quest)
- [ ] Buffer for anything that slipped

## Cut list (pull in this order when behind)

1. F11 second framework adapter
2. F10 LLM judge
3. HITL pause beat (dev path stays; just not on camera)
4. Griffin breadth (auto-discovery → hardcode 3 series; TabFM → TabPFN → MAD ladder per `07`) — Griffin **core** never cut
5. HQ Session Detail → collapse to SigNoz deep-links (server still powers threat feed + export)
6. Agent K (fleet of one is fine if J's story is tight)
7. S3 Serleena (S1 already shows tool-blocking)
8. F9 canaries

**Never cuttable:** SigNoz MCP in the Case File beat, F7 exporter, F8 Neuralyzer, Griffin core — these carry demo beats.

## Standing rules

- Provision everything as code — a judge can `docker compose up` + `./scripts/run-demo.sh`.
- Every scenario emits telemetry even when blocked — blocked-but-invisible is a failed scenario.
- **Check the submission form daily** (fields + deadline may change).
- Commit small and often; messages describe WHAT shipped.
- End of each day: 2-line status note in `docs/log.md` (what landed, what's at risk).
