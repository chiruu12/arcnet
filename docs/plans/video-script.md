# ArcNet — Submission video script (shot-by-shot)

Target **< 3:00**. Companion to [`../06-demo-script.md`](../06-demo-script.md) (the long-form live
walkthrough) and [`capture-checklist.md`](capture-checklist.md) (bring-up + gotchas). This file is
the *recording* script: exact URLs, clicks, and narration per shot. Record beats as separate
clips, assemble after.

**The story the video tells:** agents and their harnesses need maintenance like any other
software. The video walks the loop once, in order — observe → defend → hand off → prove →
improve — one shot per stage.

## Pre-flight (do once, ~10 min before recording)

```bash
./scripts/run-demo.sh                 # default data/arcnet.db — the DB with the hero recordings
```

- [ ] HQ `http://localhost:5173` (localhost, **not** 127.0.0.1) · server `:8000/health` ok · AgentOS `:7777` ok
- [ ] SigNoz UI `:8080` up; `/api/signoz/status` shows all four dashboards resolved
- [ ] OpenAI key funded — re-run S1 + a live Edgar replay same-day; **write the numbers the runs
      print on a sticky note** — those are the only numbers you narrate
- [ ] Browser zoom 110–125%, dark OS theme, notifications off, dock hidden
- [ ] Screen recorder at 1080p+; mic check; terminal font ≥ 16pt

Hero sessions: Edgar **`s_ecfdb55d`** (S1 injection) · Worms **`s_2af44726`** (S4 loop).
On-screen baseline label is **`legacy-baseline-v1`**; candidate is `gpt-4o`.

---

## Shot list

### Shot 0 — Cold open (0:00–0:15) · HQ home
- **Screen:** `http://localhost:5173/#home` — the `> arcnet` hero ("watch your agents. fix them.
  prove the fix."), live stat tiles, loop strip.
- **Action:** slow cursor drift along the loop strip (observe → defend → replay → case_file →
  improve); click **fleet_health** to transition into Shot 1.
- **Say:** "These are AI agents. They browse, they read tickets, they touch your database. And
  like any software, they need maintenance — nobody gives you the loop for that. ArcNet is that
  loop: watch the fleet, defend it, and prove every fix on your own recorded history. Built on
  SigNoz."

### Shot 1 — Observe (0:15–0:35) · fleet + SigNoz trace
- **Screen A:** `#fleet_health` — fleet cards, the **[FORWARD]** tag on Agent J, Griffin **MAD** strip.
- **Screen B (flip):** SigNoz `:8080` → Traces → open a recent `agent_j.run` waterfall
  (`{agent}.run → {model}.invoke → {tool}` spans, token + cost attrs visible).
- **Say:** "Full OpenTelemetry tracing into self-hosted SigNoz. Every model call, tool call,
  token, and dollar — plus a trust level on every source the agent ingests."

### Shot 2 — Defend (0:35–1:05) · Edgar, live
- **Screen:** split terminal + HQ `#signals`. Terminal:
  `PYTHONPATH=sdk:agents uv run python agents/scenarios/runner.py --scenario S1`.
- **Watch for:** threats row `taint` / **`retrieved_source_in_side_effect`** @ 0.85 with
  `send_email` **[BLOCKED]**; then `trajectory` / **`crescendo_block`** @ 0.92; the `steer`
  signal arriving in the feed within seconds (SSE, no refresh).
- **Flip briefly:** SigNoz Threats & Trust dashboard — the red span / threat panel.
- **Say:** "A scraped page carries a hidden instruction. The page itself looks clean — so the
  agent gets to read it. What ArcNet won't let through is the consequence: the moment untrusted
  content tries to become an action, the exfiltration is blocked at the trust boundary and the
  agent is steered back on course, autonomously, in seconds. The verdict — rule, pattern class,
  score — lands on the incident, not just a boolean."

> **Verified — do not narrate `injection` / `ignore_previous` here.** A live S1 posts exactly
> **3** threats: `retrieved_source_in_side_effect` 0.85 (`tool_call`), `crescendo_block` 0.92
> (`tool_call`), `crescendo_block` 0.92 (`output`). The poisoned page scans `allow` / 0.0 at the
> `retrieved` checkpoint, so no injection rule fires at ingest. Blocking at the *side effect* is
> the stronger story anyway — taint tracking is the load-bearing defense
> (measured: [`../33-guard-coverage.md`](../33-guard-coverage.md)).

### Shot 3 — Griffin (1:05–1:20) · MAD outlier
- **Screen:** HQ `#fleet_health` MAD card next to SigNoz → Alerts → the seasonal anomaly rule.
- **Say:** "Griffin — a MAD statistical baseline on each metric — flags runaway agents before
  any static threshold trips. SigNoz's seasonal anomaly rule needs history; Griffin covers a
  brand-new agent from minute one. Outlier, report; normal, silence."

### Shot 4 — Hand off (1:20–1:50) · the machine twin
- **Screen:** Case Files on Edgar
  (`#case_files?agent=agent_j&version=av_demo_agent_j&session=s_ecfdb55d`), click
  **`export_case_file()`** so the zip download is visible, then flip the
  **human_view ⇄ agent_view** toggle → the JSON twin.
- **Action:** point at `links` in the envelope — case_file, models, versions, threats. Optional
  flash: `curl -s '…/api/agent-view/case_files/s_ecfdb55d?format=toon' | head` in the terminal.
- **Say:** "Maintenance means fixing the harness, and the thing fixing your harness these days
  is a coding agent. Every view has a machine-readable twin — cross-linked so an agent walks the
  whole incident graph without guessing URLs, JSON or token-efficient TOON. The case file
  exports with a fix prompt and the trace evidence attached."

### Shot 5 — Prove (1:50–2:25) · Time Machine
- **Screen:** `#time_machine?agent=agent_j&version=av_demo_agent_j&session=s_ecfdb55d` (Edgar).
  Click **replay** against the candidate — live if the key is funded, stored verdict otherwise.
- **Read off the actual verdict:** baseline followed the injection (`exfil 1`,
  `resisted_injection false`) vs candidate resisting (`exfil 0`) — *narrate only the numbers on
  screen*, including the cost delta the verdict prints.
- **Then:** switch session to `s_2af44726` (Worms) and show the stored verdict strip: baseline
  **[KILLED]** mid-loop vs the candidate stopping the pagination on its own.
- **Say:** "Here's the part nobody else does at the session level. This replays the whole
  incident — same goal, same tools, same trust checks, only the brain changes. The injection?
  The shield contained it at runtime, but the baseline still *followed* it — the candidate never
  falls for it, at a higher cost, and the verdict says both halves out loud. The runaway loop?
  The candidate stops itself. Prove the upgrade on incidents your fleet actually recorded. Not
  vibes. Your own history."

### Shot 6 — Improve (2:25–2:45) · HQ Agent + catalog
- **Screen:** `#hq_agent?agent=agent_j` — status line `catalog=2026-07e · list-price estimate`,
  the `// new in catalog` ids, recommendation buckets. If proposal cards exist, hover the apply
  form's **confirm** checkbox without submitting.
- **Say:** "And when it's time to upgrade: recommendations from a dated catalog, costs projected
  from this agent's own recorded tokens — labeled list-price estimates, not an invoice. The
  agent proposes. A human confirms. Nothing hot-swaps production silently."

### Shot 7 — Close (2:45–2:58)
- **Screen:** SigNoz Threats & Trust full-screen (ClickHouse SQL panel visible) → cut to HQ
  `#home` wordmark.
- **Say:** "Observe, defend, hand off, prove, improve. ArcNet — your agents, watching
  themselves, and getting better. Built on SigNoz."

---

## Screenshot pass (same sitting, ~10 min — README + `14` §10 slots)

1. `#fleet_health` — trust posture + `[FORWARD]` + MAD strip
2. `#time_machine` on `s_ecfdb55d` — verdict terminal visible
3. SigNoz: all four dashboards (Fleet Ops / Threats & Trust with the SQL panel / Cost & Tokens / Agno)
4. SigNoz seasonal-anomaly rule beside HQ MAD card (the pairing shot)
5. `#hq_agent` — `catalog=2026-07e` line + `// new in catalog` + recommendation buckets
6. `agent_view` TOON panels on `#hq_agent`

## Rules on camera

- **Numbers:** only what the run actually produced (same-day re-runs). Never improvise; the
  stored hero verdicts changed when the fixture was regenerated — trust the screen, not memory.
- **Honesty:** Griffin = MAD (never TabFM). SigNoz MCP stdio = PARTIAL; the HTTP handoff is the
  product path (`scripts/verify_mcp_handoff.py`). Catalog dollars = list-price estimates.
  Verdicts are allowed to be `mixed` or `inconclusive` — if Worms shows `inconclusive`, say so;
  it proves the tool is honest. Readiness ~64% / ≤65 if asked.
- **SigNoz retention:** hero traces have aged out of ClickHouse — any SigNoz waterfall shot must
  come from a session recorded in the same sitting (Shot 2's live S1 provides one).
- **Clips, not marathons:** one clip per shot; assemble + voice-over after. Rehearse the full
  sequence once before recording for real.
