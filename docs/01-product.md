# ArcNet — Product (v2)

The **product spec** — the features, the loop, the demo. The concept, locked scope decisions, and landscape live in `08-vision-v2.md`; if a *scope/concept* question conflicts, `08` wins, and for *feature/spec* detail, this doc wins.

## One-liner

**ArcNet is the control plane for a self-improving agent fleet.** It watches every agent's behavior, cost, and the *trust of everything it ingests* (on SigNoz), stops attacks in real time (Unplug), makes all of it legible to the coding agents that improve the fleet (the agent-view), and lets you prove a different model or prompt would behave better before you ship it (the Time Machine).

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
2. **Detect** — two detectors. (a) *Trust:* Unplug tags every ingested datum with a trust level and scans the untrusted ones. (b) *Anomaly:* Griffin (foundation-model) flags metric outliers static thresholds miss.
3. **Defend** — an untrusted source trying to steer an agent is blocked; a `steer` signal makes the agent quarantine it and self-correct; runaway loops get `kill`.
4. **Hand off** — every incident and every panel has an **agent-view**: a goal-level, trust-annotated, structured format that a coding agent (Claude Code, Codex, Cursor) consumes to improve the observed agent. ArcNet is the substrate; the coding agents people already run are the "evolvers."
5. **Prove** — the **Time Machine** replays a recorded incident against a different model or prompt (tool outputs mocked from the trace) and shows the behavioral diff: did it resist the injection? loop less? cost less? reach the goal? Proof on your own history, not vibes.

## What we are NOT building (scope guardrails)

- **No DSPy, no GEPA, no autonomous evolver.** ArcNet *shows* how agents behave and how alternatives would behave. Humans + their existing coding agents do the improving.
- **No live re-execution** for counterfactuals — replay-from-trace with mocked tools only (deterministic, cheap, demoable).
- **Not a general eval platform** — the replay harness is scoped to the demo scenarios.

## The pillars (one homogeneous system)

### 1. Observe — SigNoz (the substrate)
Track-1 core. OTel GenAI semantic conventions + our `arcnet.*` namespace. Everything else sits on the traces/metrics/logs SigNoz already holds — including the Time Machine, which replays *from* those traces.

### 2. Trust & Shield — Unplug as source-trust monitoring
The security story is **provenance-first**, which is exactly Unplug's taint/trust model:
- Every datum an agent ingests gets a **trust level**: `user` · `retrieved`/`scraped` · `tool_output` · `external` · `system`.
- Unplug scans the **untrusted** sources — where injection actually enters. **Scraped/fetched web content is filtered before it reaches the model.**
- **Forward-facing agents** (public/user-facing, browsing, ingesting third-party content) are flagged as **higher injection-risk surfaces** — a first-class attribute in the fleet view, not an afterthought.
- Taint **propagates**: untrusted content flowing toward a sensitive tool (email, DB, payment) blocks that tool call (the Edgar exfil chain).
- Homogeneous with observability: "source trust" and "injection exposure" sit next to cost and latency as health dimensions — one product, not a bolted-on scanner.

### 3. Self-correct — signals
Alert → webhook → signal bus → Agno hook. Four kinds: `steer` (inject guidance, continue), `pause` (HITL approve/reject from the UI), `kill` (cancel a runaway), `note` (annotate telemetry only). The fleet defends itself in seconds.

### 4. Anomaly — Griffin
Foundation-model (TabFM) anomaly detection on the metrics; reports only true outliers, silent otherwise. Catches health drift on new/short-history agents that seasonal thresholds miss. (Design: `07-griffin-anomaly.md`.)

### 5. Agent-view — the machine-optimal twin
**Every datum ArcNet shows has an agent-optimal representation**, served for a coding agent to consume:
- Not raw logs — a **goal-level, trust-annotated, structured** view: what the agent was trying to do, where trust broke, what the anomaly was, the recommended fix, and a pointer to pull raw spans via the **SigNoz MCP server**.
- Served as an **ArcNet agent API** (JSON per view) and the **Case File** bundle; the SigNoz MCP underneath gives the coding agent raw trace evidence.
- The point: a Claude Code / Codex / Cursor session reads the fleet's health and incidents in *its* best format, then improves the observed agent. This is the "self-improving fleet" made real without us building an evolver.

### 6. Time Machine — counterfactual replay
- Replay a **recorded session** against a **different model/prompt**, tool outputs mocked from the trace (replay-from-trace; not live).
- Show the **behavioral diff** (resisted injection? looped less? cheaper? reached goal?) + a verdict + a recommendation.
- Turns the trace store into a **replayable proof harness**: propose a fix (agent-view/Case File → coding agent) → **replay to prove** it's better. The answer to "should I switch models / change this prompt?".

## Men in Black — as undertone, not costume
The frame stays (ArcNet = the shield around the fleet; agents are registered and monitored; a prompt-injected agent is a bug in a human suit). But execution is **product-grade**; MIB survives only as the wordmark, deadpan microcopy, and a whisper of aesthetic. Not a themed console. Frontend direction: `09-frontend.md`.

## Features, re-tiered for v2

Every P0 item carries a demo beat (`06-demo-script.md`). Feature IDs are stable build-order labels, not priority order. Numbering skips **F8** (redaction/Neuralyzer — now delivered by the output guardrail inside F2 + scenario S2, not a standalone feature) and **F12** (standalone SigNoz-MCP — folded into F7).

**P0 — demo-critical**
- F1 Instrumented fleet (SigNoz, Agno via openinference).
- F2 Trust & guard telemetry (Unplug source-trust as `UnplugGuardrail` + tool hooks; `arcnet.guard.*`).
- F3 Bug Suite scenarios (S0/S1/S2/S4/S5).
- F4 SigNoz depth (dashboards, alerts incl. seasonal anomaly, webhook).
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
- Time Machine breadth (replay the corpus of 12 recorded incidents, aggregate "candidate resists 10/12").
- F9 canaries.

**P2 — cut freely**
- F10 LLM judge · F11 second framework adapter · Agent K · S3 Serleena.

## Demo story (full script in `06`)
1. **Fleet Health** — agents on SigNoz; one flagged **forward-facing** (higher injection-risk), trust posture next to cost/latency.
2. **Edgar** — forward-facing agent scrapes a page with a hidden injection → Unplug flags the untrusted source, filters it, blocks the exfil, `steer` → self-corrects.
3. **Griffin** — token-rate outlier flagged before any static threshold (The Worms).
4. **Agent-view** — flip the incident to its machine format; hand to Claude Code/Codex → it reads the trust-annotated Case File (+ pulls raw traces via SigNoz MCP) and proposes the fix.
5. **Time Machine (the whoa)** — replay the Edgar session against a candidate model, side by side: the candidate resists where the baseline was exploited. Proof.
6. **Close** — SigNoz dashboards: every trace, dollar, and trust decision accounted for.
