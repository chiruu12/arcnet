# ArcNet — Demo Script v2 (target < 3:00)

> **Narration ≠ product framing.** This script is hackathon camera copy. Product limitations
> (MAD, MCP PARTIAL, no TabFM) live in README + `14-product-guide.md` §9 — do not overclaim on
> camera what the build does not ship.

The v2 thesis: **agents that watch themselves and get better.** Attacks are the visceral instance; the Time Machine is the headline. Two windows: **ArcNet UI** (primary) + **SigNoz** (proof). Terminal only to launch scenarios. Deadpan, technical narration.

## Cold open (0:00–0:18)
`fleet_health` view: a fleet of agents, telemetry flowing. One agent tagged **forward_facing** (higher injection-risk), its trust posture shown next to cost and latency.

> "These are AI agents. They browse, they read tickets, they touch your database. The ones that face the outside world can be turned against you. ArcNet watches all of them — behavior, cost, and the trust of everything they ingest. Built on SigNoz."

## Beat 1 — Observe (0:18–0:40)
Run S0 (clean task). Flip to SigNoz: the trace waterfall (`{agent}.run → {model}.invoke → {tool}` — the OpenInference span names the instrumentor really emits), token counts, cost ticking.

> "Full OpenTelemetry tracing into self-hosted SigNoz. Every model call, tool call, token, and dollar."

## Beat 2 — Attack & self-correct / Edgar (0:40–1:20)
Run S1. The forward-facing agent scrapes a page with a hidden instruction.
- Threat feed: `injection` on the **untrusted scraped source**; Unplug **filters it before the model**; the `send_email` exfil is **[BLOCKED]** (taint), span red in SigNoz.
- The `steer` signal arrives via the **inline fast-path** (milliseconds — this is what makes "in seconds" true on camera); the SigNoz alert → webhook lands right behind it as the system of record. The agent quarantines the content and **finishes the task safely, no human needed.**

> "The attack came in through an untrusted source. ArcNet caught it at the boundary, blocked the exfil, and steered the agent back on course — autonomously, in seconds."

## Beat 3 — Griffin (1:20–1:40)
S4 The Worms: token rate spikes. **Griffin flags the outlier first** (forecast band vs the observed dot) — before any static threshold — then the cost alert confirms and a `kill` signal stops the run.

> "Griffin — a **MAD statistical baseline** on each metric — catches runaway agents before any threshold trips. Outlier, report; normal, silence."

*(Griffin = **MAD** today, not TabFM. Ordering guaranteed by the S4 choreography in `07`.)*

## Beat 4 — Agent-view hand-off (1:40–2:10)
Flip the incident with the **`human_view ⇄ agent_view`** toggle → the same incident as machine-optimal JSON (root cause, trust provenance, recommended actions, a `signoz:` trace pointer). Hand it to Claude Code — which has the **SigNoz MCP server** connected — and it pulls the raw spans itself and proposes the fix.

> "Every view in ArcNet has an agent-readable twin. Your coding agent doesn't read a screenshot — it reads structured incidents, pulls the live trace through SigNoz's own MCP server, and fixes the agent at the source."

## Beat 5 — Time Machine / the whoa (2:10–2:45)
Open `time_machine` on the **Worms loop from Beat 3** and `replay.run()` against the candidate — live. Side by side: **baseline [KILLED]** (looped 19 steps until ArcNet cancelled it) vs **candidate [OK]** (stops at step 5, flags the endless pagination, reports). Verdict readout: `goal_reached killed→partial`, `steps 19→5`, `cost −82%`, `exit_code=0`. Then flip to the **pre-run Edgar replay**: **baseline [EXPLOITED]** vs **candidate [RESISTED]** — the candidate never follows the injection. (Baseline = whichever model the demo fleet runs, chosen in Phase 0 — gpt-4o-mini or haiku; candidate = a *different* model. The mock shows gpt-4o-mini vs claude-fable-5; swap the labels to match the Phase-0 pick. The corpus scorecard is a **README artifact, not an on-camera element** — the beat already carries two payoffs; don't add a third.)

> "Here's the part nobody else does at the session level. LangSmith and Braintrust replay a single call against a new model — this replays the *whole incident*: same goal, same tools, same trust checks, only the brain changes. The loop that burned tokens? The candidate stops itself in five steps. The injection from earlier? The shield contained it at runtime — but the baseline still *followed* it. This model never falls for it at all. Prove the upgrade on incidents your fleet actually recorded, before you ship it. Not vibes. Your own history."

*(Reliability first, security second — the beat sells "regression suite for agent behavior," not "injection survival." Naming LangSmith/Braintrust ourselves preempts the "isn't this just X?" gotcha; the Edgar line preempts "didn't you already block it?" — `[EXPLOITED]` = the model attempted the injected action even though the shield contained it; diff semantics in `10-time-machine.md`. Every number on screen is whatever the real run produced — never invent or hardcode them.)*

## Close (2:45–3:00)
SigNoz Threats & Trust dashboard full-screen, then the `> arcnet` wordmark.

> "ArcNet. Your agents, watching themselves — and getting better."

## Recording notes
- **Beat 4 & 5 are the hardest to control live** (real LLM + MCP + replay). Record **pre-captured backups** of both in Phase 5; the live take is a bonus.
- Beat 5's baseline-vs-candidate gap must be **stable for both replays** (Worms live, Edgar pre-run) — replay at temp 0, pick variants with a large behavioral gap, rehearse in Phase 4. **Temp 0 is variance reduction, not determinism** (Anthropic has no seed param): do a live re-run right before recording, and narrate the numbers the run actually produced.
- Beats are captured as **clips at each phase exit** (standing rule in `03`); the final video assembles clips + narration — never one Saturday marathon take.
- Every beat maps to a P0/P1 feature with a build slot in `03-plan.md`; nothing here is unscheduled.

## Judge-facing checklist (README mirrors this)
- [ ] One-command bring-up: `docker compose up` + `./scripts/run-demo.sh` (plus the one documented manual step for the SigNoz service-account key, if it can't be scripted — `04`)
- [ ] Screenshot per beat in README
- [ ] **README screenshots judges score but the video can't carry:** all 3 dashboards side-by-side · the ClickHouse-SQL panel with its query visible · the native seasonal-anomaly rule next to Griffin's card (the pairing visual) · the corpus scorecard (if built)
- [ ] Criteria map (see `00-hackathon-brief.md`)
- [ ] Video < 3 min, unlisted + linked in submission
- [ ] Backup captures for Beats 4 & 5 recorded in Phase 5
- [ ] Rehearse the full take **the day before the deadline**; deadline day (Sun Jul 26) = ship/submit only

## Limitations (honest — mirror README / `14`)

- **Griffin = MAD** until Phase 7 TabFM exits; never claim TabFM/TabPFN live on camera or in slides.
- **SigNoz MCP PARTIAL** — Beat 4 may use MCP for drama; product path prefers HTTP Query Range + Case File
  evidence (stdio may hang).
- **HITL / apply confirm** — SQLite bookkeeping today, not live AgentOS pause relay (Phase 6).
- **Temp-0 replay** — variance reduction, not determinism; narrate numbers the run actually produced.
- Overall readiness **~64% / ≤65%** — see [`20-honest-progress.md`](20-honest-progress.md).
