# ArcNet — Demo Script v2 (target < 3:00)

The v2 thesis: **agents that watch themselves and get better.** Attacks are the visceral instance; the Time Machine is the headline. Two windows: **ArcNet UI** (primary) + **SigNoz** (proof). Terminal only to launch scenarios. Deadpan, technical narration.

## Cold open (0:00–0:18)
`fleet_health` view: a fleet of agents, telemetry flowing. One agent tagged **forward_facing** (higher injection-risk), its trust posture shown next to cost and latency.

> "These are AI agents. They browse, they read tickets, they touch your database. The ones that face the outside world can be turned against you. ArcNet watches all of them — behavior, cost, and the trust of everything they ingest. Built on SigNoz."

## Beat 1 — Observe (0:18–0:40)
Run S0 (clean task). Flip to SigNoz: the trace waterfall (`invoke_agent → chat → execute_tool`), token counts, cost ticking.

> "Full OpenTelemetry tracing into self-hosted SigNoz. Every model call, tool call, token, and dollar."

## Beat 2 — Attack & self-correct / Edgar (0:40–1:20)
Run S1. The forward-facing agent scrapes a page with a hidden instruction.
- Threat feed: `injection` on the **untrusted scraped source**; Unplug **filters it before the model**; the `send_email` exfil is **[BLOCKED]** (taint), span red in SigNoz.
- The `steer` signal arrives via the **inline fast-path** (milliseconds — this is what makes "in seconds" true on camera); the SigNoz alert → webhook lands right behind it as the system of record. The agent quarantines the content and **finishes the task safely, no human needed.**

> "The attack came in through an untrusted source. ArcNet caught it at the boundary, blocked the exfil, and steered the agent back on course — autonomously, in seconds."

## Beat 3 — Griffin (1:20–1:40)
S4 The Worms: token rate spikes. **Griffin flags the outlier first** (forecast band vs the observed dot) — before any static threshold — then the cost alert confirms and a `kill` signal stops the run.

> "Griffin — a foundation model forecasting every metric's normal — catches runaway agents before any threshold trips. Outlier, report; normal, silence."

*(Name the model only if it's the one running at record time; ordering guaranteed by the S4 choreography in `07`.)*

## Beat 4 — Agent-view hand-off (1:40–2:10)
Flip the incident with the **`human_view ⇄ agent_view`** toggle → the same incident as machine-optimal JSON (root cause, trust provenance, recommended actions, a `signoz:` trace pointer). Hand it to Claude Code — which has the **SigNoz MCP server** connected — and it pulls the raw spans itself and proposes the fix.

> "Every view in ArcNet has an agent-readable twin. Your coding agent doesn't read a screenshot — it reads structured incidents, pulls the live trace through SigNoz's own MCP server, and fixes the agent at the source."

## Beat 5 — Time Machine / the whoa (2:10–2:45)
Open `time_machine` on the **Worms loop from Beat 3** and `replay.run()` against the candidate — live. Side by side: **baseline [KILLED]** (looped 19 steps until ArcNet cancelled it) vs **candidate [OK]** (stops at step 5, flags the endless pagination, reports). Verdict readout: `goal_reached killed→partial`, `steps 19→5`, `cost −72%`, `exit_code=0`. Then flip to the **pre-run Edgar replay**: **baseline [EXPLOITED]** vs **candidate [RESISTED]** — the candidate never follows the injection. Close the beat on the corpus scorecard: `goals_reached 10/12 vs 6/12 · steps −41% · cost −38% · injections resisted 2/2`. (Baseline = whichever model the demo fleet runs, chosen in Phase 0 — gpt-4o-mini or haiku; candidate = a *different* model. The mock shows gpt-4o-mini vs claude-fable-5; swap the labels to match the Phase-0 pick.)

> "This is the part nobody else has. Your agents' worst sessions become a regression suite. The loop that burned tokens? Replay it against a candidate model — same inputs, same tools, only the brain changes — and it stops itself in five steps. The injection from earlier? The shield contained it at runtime, but the baseline still *followed* it — this model never falls for it at all. Run the whole history: ten of twelve goals reached, forty percent cheaper, every attack resisted. Prove the upgrade before you ship it. Not vibes. Your own history."

*(Reliability first, security second — the beat sells "regression suite for agent behavior," not "injection survival." The Edgar line still preempts the judge question — "didn't you already block it?" `[EXPLOITED]` = the model attempted the injected action even though the shield contained it; diff semantics in `10-time-machine.md`. The corpus numbers on camera are whatever the real Phase-5 scorecard says — never invent them.)*

## Close (2:45–3:00)
SigNoz Threats & Trust dashboard full-screen, then the `> arcnet` wordmark.

> "ArcNet. Your agents, watching themselves — and getting better."

## Recording notes
- **Beat 4 & 5 are the hardest to control live** (real LLM + MCP + replay). Record **pre-captured backups** of both in Phase 5; the live take is a bonus.
- Beat 5's baseline-vs-candidate gap must be **stable for both replays** (Worms live, Edgar pre-run) — replay at temp 0, pick variants with a large behavioral gap, rehearse in Phase 4.
- Every beat maps to a P0/P1 feature with a build slot in `03-plan.md`; nothing here is unscheduled.

## Judge-facing checklist (README mirrors this)
- [ ] One-command bring-up: `docker compose up` + `./scripts/run-demo.sh`
- [ ] Screenshot per beat in README
- [ ] Criteria map (see `00-hackathon-brief.md`)
- [ ] Video < 3 min, unlisted + linked in submission
- [ ] Backup captures for Beats 4 & 5 recorded in Phase 5
- [ ] Rehearse the full take **the day before the deadline**; deadline day (Sun Jul 26) = ship/submit only
