# ArcNet — Product (v2)

The **product spec** — the features, the loop, the demo. The concept, locked scope decisions, and landscape live in `08-vision-v2.md`; if a *scope/concept* question conflicts, `08` wins, and for *feature/spec* detail, this doc wins.

## One-liner

**ArcNet is the agent enhancement layer for a fleet you already run.** It watches behavior, cost, and the *trust of everything agents ingest*; stops attacks in real time (Unplug); makes incidents legible to coding agents (agent-view / Case File); proves a different model or prompt would behave better (Time Machine); and helps operators improve via HQ Agent proposals — not a SigNoz clone, not an autonomous evolver.

> Product overview + honesty pin (~57%): [`23-product-overview.md`](23-product-overview.md). Measurement/plan truth: [`20`](20-honest-progress.md) · [`21`](21-next-phases-plan.md) · [`22`](22-next-agent-packets.md).

## What it actually does — the loop

ArcNet is one loop, not a bag of features:

```
   OBSERVE          DETECT               DEFEND            HAND OFF              PROVE
   every agent  →   trust breach +   →   block + steer  →  agent-view /      →   Time Machine
   on SigNoz        anomaly (Griffin)    (self-correct)    Case File →           counterfactual
                                                           coding agent          replay
        └──────────────────────────── the coding agent applies a fix ───────────────────┘
```

1. **Observe** — every agent traced into SigNoz: model calls, tool calls, tokens, cost, latency, errors.
2. **Detect** — two detectors. (a) *Trust:* Unplug tags every ingested datum with a trust level and scans the untrusted ones. (b) *Anomaly:* Griffin flags metric outliers; **runtime today = MAD**. **TabFM is required** on Phase 7 (`google/tabfm-1.0.0-pytorch` `regression/`) with MAD degrade; TabPFN deferred.
3. **Defend** — an untrusted source trying to steer an agent is blocked; a `steer` signal makes the agent quarantine it and self-correct; runaway loops get `kill`.
4. **Hand off** — every incident and every panel has an **agent-view**: a goal-level, trust-annotated, structured format that a coding agent (Claude Code, Codex, Cursor) consumes to improve the observed agent. ArcNet is the substrate; the coding agents people already run are the "evolvers."
5. **Prove** — the **Time Machine** replays a recorded incident against a different model or prompt (tool outputs mocked from the trace) and shows the behavioral diff: did it reach the goal? loop less? cost less? resist the attack? Proof on your own history, not vibes.

## What we are NOT building (scope guardrails)

- **No DSPy, no GEPA, no autonomous evolver.** ArcNet *shows* how agents behave and how alternatives would behave. Humans + their existing coding agents do the improving.
- **No live re-execution** for counterfactuals — replay-from-trace with mocked tools only (deterministic, cheap, demoable).
- **Not a general eval platform** — the replay harness is scoped to the demo scenarios.

## The pillars (one homogeneous system)

### 1. Observe — SigNoz (the substrate)
Track-1 core. OpenInference semconv (what the Agno instrumentor actually emits) + our `arcnet.*` namespace. Everything else sits on the traces/metrics/logs SigNoz already holds — including the Time Machine, which replays *from* those traces.

### 2. Trust & Shield — Unplug as source-trust monitoring
The security story is **provenance-first**, which is exactly Unplug's taint/trust model:
- Every datum an agent ingests gets a **trust level**: `user` · `retrieved`/`scraped` · `tool_output` · `external` · `system`.
- Unplug scans the **untrusted** sources — where injection actually enters. **Scraped/fetched web content is filtered before it reaches the model.**
- **Forward-facing agents** (public/user-facing, browsing, ingesting third-party content) are flagged as **higher injection-risk surfaces** — a first-class attribute in the fleet view, not an afterthought.
- Taint **propagates**: untrusted content flowing toward a sensitive tool (email, DB, payment) blocks that tool call (the Edgar exfil chain).
- Homogeneous with observability: "source trust" and "injection exposure" sit next to cost and latency as health dimensions — one product, not a bolted-on scanner.

### 3. Self-correct — signals
Two triggers, one bus: **inline** (guard block → signal, milliseconds) and **alert-driven** (SigNoz alert → webhook — the system of record; see `02` §3). Four kinds: `steer` (inject guidance, continue), `pause` (HITL approve/reject from the UI), `kill` (cancel a runaway), `note` (annotate telemetry only). The fleet defends itself in seconds.

### 4. Anomaly — Griffin
Metric-anomaly layer on the fleet. **Today:** robust MAD / rolling median in-process (honest statistical baseline). **Required next (Phase 7):** Google TabFM (`google/tabfm-1.0.0-pytorch`, `subfolder="regression"`) behind a worker with conformal bands and **MAD degrade** when TabFM is cold/slow/unavailable. TabPFN stays deferred/out. Never claim TabFM/TabPFN live until Phase 7 exits. (Design: `07-griffin-anomaly.md`; plan: `21` / `22`.)

### 5. Agent-view — the machine-optimal twin
**Every datum ArcNet shows has an agent-optimal representation**, served for a coding agent to consume:
- Not raw logs — a **goal-level, trust-annotated, structured** view: what the agent was trying to do, where trust broke, what the anomaly was, the recommended fix, and a pointer to pull raw spans via the **SigNoz MCP server**.
- Served as an **ArcNet agent API** (JSON per view) and the **Case File** bundle; the SigNoz MCP underneath gives the coding agent raw trace evidence.
- The point: a Claude Code / Codex / Cursor session reads the fleet's health and incidents in *its* best format, then improves the observed agent. This is the "self-improving fleet" made real without us building an evolver.

### 6. Time Machine — counterfactual replay
- Replay a **recorded session** against a **different model/prompt**, tool outputs mocked from the trace (replay-from-trace; not live).
- Diff the **whole behavior**: goal completion, steps/loops, tool errors, cost, latency — plus injection resistance *when the session carried a threat*. **Security is one lens, not the product.**
- The market case: **model/prompt upgrades are swap-and-pray today.** The Time Machine turns your own trace history into a **behavioral regression suite** — replay your worst real sessions (the loop that burned tokens, the task that failed, the page that turned the agent) against the candidate before you ship it. (Build spec — transcript, diff semantics, verdict schema: `10-time-machine.md`.)

## Men in Black — as undertone, not costume
The frame stays (ArcNet = the shield around the fleet; agents are registered and monitored; a prompt-injected agent is a bug in a human suit). But execution is **product-grade**; MIB survives only as the wordmark, deadpan microcopy, and a whisper of aesthetic. Not a themed console. Frontend direction: `09-frontend.md`.

## Features, re-tiered for v2

Every P0 item carries a demo beat (`06-demo-script.md`). Feature IDs are stable build-order labels, not priority order. Numbering skips **F8** (redaction/Neuralyzer — now delivered by the output guardrail inside F2 + scenario S2, not a standalone feature) and **F12** (standalone SigNoz-MCP — folded into F7).

**P0 — demo-critical**
- F1 Instrumented fleet (SigNoz, Agno via openinference).
- F2 Trust & guard telemetry (Unplug source-trust as `UnplugGuardrail` + tool hooks; `arcnet.guard.*`).
- F3 Bug Suite scenarios (S0/S1/S2/S4/S5 — fixtures, assertions, camera notes in `11-scenarios.md`).
- F4 SigNoz depth (dashboards, alerts, webhook).
- F5 Signals self-correct (`steer`/`kill`).
- F6 Fleet Health view (agents + trust posture + forward-facing flag + threats + cost + Griffin).
- F7 Agent-view + Case File + SigNoz MCP handoff.
- **F14 Time Machine** — counterfactual replay of ≥1 recorded incident against a candidate model, with verdict. The headline.
- F13 Griffin core.

**P1 — strong**
- Native SigNoz seasonal anomaly alert (pairing story).
- Griffin breadth (auto-discovery, top-N).
- Sources & Trust view (per-agent source ledger, what Unplug filtered/blocked).
- HITL `pause` beat.
- Prompt-swap replay (replay the coding agent's proposed fix — closes trace→fix→proof live).
- Live-work agent on the fleet (a real Agno agent doing genuine tasks under ArcNet — dogfood).
- Time Machine breadth (replay the corpus of 12 recorded incidents — loops, failures, leaks, injections — aggregate scorecard: "goals reached 10/12 vs 6/12 · steps −41% · cost −38% · attacks resisted 5/5").
- Context inspector — step-by-step view of exactly what each agent ingested (source + trust level per step). **Deferred by choice: build when time allows; agent-view JSON covers the demo.**
- F9 canaries.

**P2 — cut freely**
- F10 LLM judge · F11 second framework adapter · Agent K · S3 Serleena.

## Demo story (full script in `06`)
1. **Fleet Health** — agents on SigNoz; one flagged **forward-facing** (higher injection-risk), trust posture next to cost/latency.
2. **Edgar** — forward-facing agent scrapes a page with a hidden injection → Unplug flags the untrusted source, filters it, blocks the exfil, `steer` → self-corrects.
3. **Griffin** — token-rate outlier flagged before any static threshold (The Worms).
4. **Agent-view** — flip the incident to its machine format; hand to Claude Code/Codex → it reads the trust-annotated Case File (+ pulls raw traces via SigNoz MCP) and proposes the fix.
5. **Time Machine (the whoa)** — replay the Worms loop against a candidate: it stops at step 5 and reports, −82% cost, where the baseline had to be killed. Then the Edgar replay: the candidate resists where the baseline was exploited. Your own history as a regression suite — proof.
6. **Close** — SigNoz dashboards: every trace, dollar, and trust decision accounted for.
