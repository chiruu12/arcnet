# ArcNet — Submission video script (shot-by-shot)

Target **< 3:00**. Companion to [`../06-demo-script.md`](../06-demo-script.md) (beats + framing) and
[`capture-checklist.md`](capture-checklist.md) (bring-up + gotchas). This file is the *recording*
script: exact URLs, clicks, and narration per shot. Record beats as separate clips, assemble after.

## Pre-flight (do once, ~10 min before recording)

```bash
./scripts/run-demo.sh                 # default data/arcnet.db — the DB with the hero recordings
```

- [ ] HQ `http://localhost:5173` (localhost, **not** 127.0.0.1) · server `:8000/health` ok · AgentOS `:7777` ok
- [ ] SigNoz UI `:8080` up; `/api/signoz/status` shows all four dashboards resolved
- [ ] OpenAI key funded — `uv run python scripts/phase4_g4_check.py --s1 s_ecfdb55d --s4 s_2af44726` re-run same-day; **write the numbers it prints on a sticky note** — those are the only numbers you narrate
- [ ] Browser zoom 110–125%, dark OS theme, notifications off, dock hidden
- [ ] Screen recorder at 1080p+; mic check; terminal font ≥ 16pt

Hero sessions: Edgar **`s_ecfdb55d`** (S1 injection) · Worms **`s_2af44726`** (S4 loop).

---

## Shot list

### Shot 0 — Cold open (0:00–0:15) · HQ home
- **Screen:** `http://localhost:5173/#home` — the `> arcnet` hero, live stat tiles, loop strip.
- **Action:** slow cursor drift over the loop strip (observe → defend → replay → case_file → improve); click **fleet_health** on the strip to transition into Shot 1.
- **Say:** "These are AI agents. They browse, they read tickets, they touch your database. ArcNet watches all of them — behavior, cost, and the trust of everything they ingest. Built on SigNoz."

### Shot 1 — Observe (0:15–0:35) · fleet + SigNoz trace
- **Screen A:** `#fleet_health` — fleet cards, the **forward_facing** tag on Agent J, Griffin **MAD** strip.
- **Screen B (flip):** SigNoz `:8080` → Traces → open a recent `agent_j.run` waterfall (`{agent}.run → {model}.invoke → {tool}` spans, token + cost attrs visible).
- **Say:** "Full OpenTelemetry tracing into self-hosted SigNoz. Every model call, tool call, token, and dollar — plus a trust level on every source the agent ingests."

### Shot 2 — Attack & self-correct (0:35–1:10) · Edgar
- **Screen:** split terminal + HQ `#signals`. Terminal: `PYTHONPATH=sdk:agents uv run python agents/scenarios/runner.py --scenario S1`.
- **Watch for:** threats row `injection` with the **rule name** (`ignore_previous` class) in the guard columns; `send_email` **[BLOCKED]**; the `steer` signal arriving in the feed within seconds (SSE, no refresh).
- **Flip briefly:** SigNoz Threats & Trust dashboard — the red span / threat panel.
- **Say:** "A scraped page carries a hidden instruction. ArcNet catches it at the trust boundary, blocks the exfiltration, and steers the agent back on course — autonomously, in seconds. The guard verdict — rule, pattern class, score — is recorded on the incident, not just a boolean."

### Shot 3 — Griffin (1:10–1:30) · MAD outlier
- **Screen:** HQ `#fleet_health` MAD card next to SigNoz → Alerts → the seasonal anomaly rule.
- **Say:** "Griffin — a MAD statistical baseline on each metric — flags runaway agents before any static threshold trips. SigNoz's seasonal anomaly rule needs history; Griffin covers a brand-new agent from minute one. Outlier, report; normal, silence."

### Shot 4 — Agent-view hand-off (1:30–2:00) · the machine twin
- **Screen:** Case Files on Edgar (`#case_files`, session `s_ecfdb55d`), then flip the **human_view ⇄ agent_view** toggle → the JSON twin.
- **Action:** point at `links` in the envelope — case_file, models, versions, threats — then hit `http://127.0.0.1:8000/api/agents/agent_j/model-intel` in a browser tab: catalog candidates, projected cost deltas, the reasoning-tier recommendation with its recorded evidence.
- **Say:** "Every view has a machine-readable twin, cross-linked so a coding agent can walk the whole incident graph without guessing URLs. And when it's ready to improve the agent, ArcNet recommends models from a dated catalog — cost projections computed from this agent's own recorded tokens, reasoning tiers recommended off its recorded threat rate. No fabricated benchmarks."

### Shot 5 — Time Machine (2:00–2:40) · the whoa
- **Screen:** `#time_machine` → cascade agent_j → session `s_2af44726` (Worms). Click **replay** against the candidate model — live.
- **Read off the actual verdict:** baseline **[KILLED]** vs candidate stopping early; steps, cost delta, `goal_reached` — *narrate only the numbers on screen*.
- **Then:** switch session to `s_ecfdb55d` (Edgar) and show the stored verdict: baseline attempted the injected action, candidate **resisted**.
- **Say:** "Here's the part nobody else does at the session level. This replays the whole incident — same goal, same tools, same trust checks, only the brain changes. The loop that burned tokens? The candidate stops itself in five steps. The injection? The baseline still *followed* it — this model never falls for it. Prove the upgrade on incidents your fleet actually recorded. Not vibes. Your own history."

### Shot 6 — Close (2:40–2:55)
- **Screen:** SigNoz Threats & Trust full-screen (ClickHouse SQL panel visible) → cut to HQ `#home` wordmark.
- **Say:** "ArcNet. Your agents, watching themselves — and getting better. Built on SigNoz."

---

## Screenshot pass (same sitting, ~10 min — README + `14` §10 slots)

1. `#fleet_health` — trust posture + `[FORWARD]` + MAD strip
2. `#time_machine` on `s_ecfdb55d` — verdict terminal visible
3. SigNoz: all four dashboards (Fleet Ops / Threats & Trust with the SQL panel / Cost & Tokens / Agno)
4. SigNoz seasonal-anomaly rule beside HQ MAD card (the pairing shot)
5. NEW: `model-intel` response in the HqAgent models section (catalog + Δ cost + reasoning rec)

## Rules on camera

- **Numbers:** only what the run actually produced (`docs/_phase4_g4.json` + today's re-run). Never improvise.
- **Honesty:** Griffin = MAD (TabFM only if the Phase-7 worker is live-verified before recording — otherwise don't mention it). MCP = drama, not the dependency. Readiness ~64% / ≤65 if asked.
- **Clips, not marathons:** one clip per shot; assemble + voice-over after. Rehearse the full sequence once before recording for real.
