# ArcNet — Product Vision v2 (homogeneous concept)

The **vision & decision record**: why we're building this, the locked scope decisions, and the landscape. `01-product.md` is the product spec (the features). If a *scope/concept* question conflicts, this doc wins; for *feature/spec* detail, `01` wins. Output of an office-hours session + landscape research (2026).

## One thesis

**ArcNet watches an agent fleet — its behavior, its cost, and the trust of everything it ingests — and makes that legible to both humans (the dashboard) and to the coding agents that improve them (the agent-view), with a time-machine to prove a different model or prompt would have behaved better.**

Everything below is one loop, not separate features:

```
observe ──▶ detect ──▶ self-correct ──▶ hand off ──▶ prove
(SigNoz)   (trust +     (Agno hooks)    (agent-view/  (time-machine
           anomaly)                     Case File →    counterfactual
                                        coding agent)  replay)
```

## North star & success criteria

**North star: win Track 1 by being the only entry that closes the loop — observe → detect → self-correct → hand off → prove — on a judge's own machine in two commands.**

What "done and winning" looks like, concretely:
1. **All six demo beats recorded** with backups; no beat depends on luck (choreography for S4 ordering, fast-path for Edgar's steer, 3-run majority for the replay verdict).
2. **A judge reproduces it**: `docker compose up` + `./scripts/run-demo.sh` — nothing manual, `.env.example` complete.
3. **Every judging criterion has a visible artifact** (map in `00-hackathon-brief.md`) — nothing scored on our say-so.
4. **The two "nobody else has" claims stay defensible**: agent-view (machine-optimal twin of every datum) and the Time Machine (counterfactual replay with a precise, honest verdict — `10-time-machine.md`).

**Tradeoff order when time runs short** (pre-decided so mid-build cuts are mechanical): demo-beat integrity > SigNoz depth > UI breadth > feature breadth. The cut list in `03-plan.md` implements this.

## Why this is the lovable version (landscape-grounded)

- The whole field (LangSmith, Langfuse, Arize, Braintrust, AgentOps) admits it: *nobody closes the loop from production trace → failure → fix → proof → regression*, and their data model treats agents as "sequences of LLM calls," not goal-level sessions. That gap is the wedge.
- Every observability tool is built for **humans to look at**; agent-querying is bolted on as raw-log access. ArcNet flips it: **the primary consumer of agent observability is the agent that will improve the fleet.** Dashboard = the human's window into an agent-to-agent loop.
- Prior art proves the pieces are buildable: counterfactual **replay-from-trace** (Causal Agent Replay, 2026) and coding agents that already ingest traces to self-evolve. We ride those, we don't rebuild them.

## The market pains this maps to (needed, not neat)

Ranked by how universally teams running agents actually feel them:

1. **Agents don't reliably finish tasks** — the #1 production blocker. Sessions fail silently; nobody can see *where* or prove a change helps. → observe + goal-level agent-view + replay.
2. **Loops and cost blowouts** — every team has the "agent burned $400 over the weekend" story; budget alerts fire *after* the damage. → Griffin (catches drift in minutes) + `kill` signals + the loop replay.
3. **Model/prompt upgrades are blind** — deprecations and price changes force migrations, and today the process is swap-and-pray. → the Time Machine as a **behavioral regression suite over your own traces**. This is the prove-pillar's core market case; injection resistance is *one dimension* of the scorecard, not the headline.
4. **Untrusted content is the new attack surface** — forward-facing agents ingest the open web (OWASP LLM01). → Unplug source-trust. The visceral demo instance, deliberately not the whole story.

One product sentence: **flight recorder + shield + wind tunnel** for agent fleets.

## Scope decisions (locked)

- **Spine:** unified "self-improving fleet." Security/attacks are the visceral demo instance; self-improvement is the frame. (D1)
- **Loop depth:** replay + propose + prove. **No DSPy, no autonomous evolver.** ArcNet *shows* how an agent performs and how a different model/prompt would perform; humans + their existing coding agents (Claude Code, Codex, Cursor) act on it. (D2 + user refinement)
- **Unplug = source-trust monitoring** (the security spine, not a bolt-on): trust level per ingested source; scan the untrusted (scraped/retrieved/external/tool-output); flag **forward-facing agents** as higher injection-risk; filter scraped content before the model sees it.

## The pillars, as one homogeneous system

### 1. Observe — SigNoz (unchanged substrate)
Every agent traced: LLM calls, tool calls, tokens, cost, latency, errors. OTel GenAI semconv + `arcnet.*`. This is the Track-1 SigNoz core; everything else sits on it.

### 2. Trust & Shield — Unplug as source-trust monitoring (sharpened)
The security story is now **provenance-first**, which is exactly Unplug's taint/trust model:
- Every datum an agent ingests is tagged with a **trust level**: `user` · `retrieved`/`scraped` · `tool_output` · `external` · `system`.
- Unplug scans the **untrusted** sources — where injection actually enters. Scraped/fetched web content is **filtered before it reaches the model**.
- **Forward-facing agents** (public/user-facing, browsing, ingesting third-party content) are flagged as **higher-risk injection surfaces** — a first-class health attribute in the fleet view.
- Taint propagates: if an untrusted source's content flows toward a sensitive tool (email, DB, payment), that tool call is blocked (the Edgar exfil chain).
- **This is homogeneous with observability**: "source trust" and "injection exposure" are health dimensions per agent, shown next to cost and latency — not a separate security product.

### 3. Self-correct — signals (unchanged)
Untrusted source tries to steer the agent → block + `steer` signal → agent quarantines and continues (Agno hooks). `kill` for runaway loops. The fleet defends itself in real time.

### 4. Anomaly — Griffin (unchanged)
FM (TabFM) anomaly detection on the metrics; reports only true outliers. Covers the "unknown-unknown" health drift static rules miss.

### 5. Agent-view — the machine-optimal twin (NEW, core to the thesis)
**Every datum the dashboard shows has an agent-optimal representation** served for consumption by a coding agent:
- Not raw logs. A **goal-level, trust-annotated, structured** view: what the agent was trying to do, where trust broke, what the anomaly was, what the suggested fix is.
- Served two ways (decide in build): an **ArcNet agent API / MCP** the coding agent calls, and the **Case File** bundle (markdown + JSON + trace IDs) it reads. The existing **SigNoz MCP** still lets the coding agent pull raw trace evidence underneath.
- The point: a Claude Code / Codex / Cursor session can read the fleet's health and incidents in the format that's best *for it*, then improve the observed agent. ArcNet is the substrate for the "evolving agent" people already run.

### 6. Time-machine — counterfactual replay (NEW, the "whoa")
- Take a **recorded session** (from traces) and **replay it against a different model or prompt**, with tool outputs mocked (replay-from-trace — feasible, deterministic, cheap; not live re-execution).
- **Show the full behavioral diff**: did model B reach the goal model A fumbled? Loop less? Cost less? Make fewer tool errors? And — when the session carried a threat — resist the injection that turned model A? **Security is one dimension of the scorecard, not the product.**
- This turns the trace store into a **behavioral regression suite**: propose a fix (agent-view/Case File → coding agent) → **replay to prove** it behaves better. Quantified, on the user's own history — the answer to "should I switch models / change this prompt?" that today is answered by swap-and-pray.

## The demo, homogeneously (full script in `06-demo-script.md`)

1. **Fleet health**: agents traced in SigNoz; one is **forward-facing** (flagged higher-risk). Trust posture visible next to cost/latency.
2. **Attack (Edgar)**: forward-facing agent scrapes a page with a hidden injection → Unplug flags the **untrusted source**, filters it, blocks the exfil, `steer` signal → agent self-corrects. All in SigNoz.
3. **Griffin**: a token-rate outlier flagged before any static threshold (The Worms).
4. **Agent-view**: flip the incident to its machine format; hand it to Claude Code/Codex — it reads the trust-annotated Case File (+ pulls raw traces via SigNoz MCP) and proposes the fix.
5. **Time-machine (the whoa)**: replay the Worms loop against a second model — it stops itself and reports where model A had to be killed, at a fraction of the cost; then the Edgar replay — model B resists where model A was exploited. Your own history as a regression suite. Proof, not vibes.
6. **Close**: SigNoz dashboards — every trace, dollar, and trust decision accounted for.

## Frontend

Complete rebuild (the v1 mock is retired). New information architecture built around the loop, not a static ops console:
- **Fleet Health** — agents + trust posture (forward-facing flagged) + threats + cost + Griffin anomalies.
- **Time Machine** (the star) — scrub a recorded session; launch a counterfactual replay against model/prompt B; side-by-side behavior diff.
- **Sources & Trust** — the data sources each agent ingested, trust levels, what Unplug filtered/blocked.
- **Agent-view toggle** — everywhere: flip any panel to the machine-optimal format a coding agent consumes.
- Aesthetic: decided in D3. MIB stays as a restrained, serious undertone (naming, deadpan copy), execution at product grade — not campy.

## What we are explicitly NOT building
- No DSPy / GEPA integration, no autonomous prompt evolution engine.
- No live re-execution for counterfactuals (replay-from-trace only).
- No general eval platform — the replay harness is scoped to the demo scenarios.
