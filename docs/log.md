# Build log

## Day 0 — Mon Jul 20 (planning)

**v1 (initial):** docs 00–07 + first mock; framing = agent security + observability dashboard on SigNoz (Agno + unplug-ai + Griffin/TabFM + signals + Case File). Review pass fixed the calendar (Jul 20 = **Mon**, deadline **Sun Jul 26**), re-tiered so the demo rides on P0, rebalanced Phase 4, moved TabFM spike to Day 0 / seed.py to Phase 3, added S4 "Griffin-first" choreography, pinned the signal schema, enumerated the env surface. Deps verified installable.

**v2 pivot (office-hours + landscape):** reframed to **"agents that watch themselves and get better"** — the control plane for a self-improving fleet. Locked: unified spine (security = visceral demo, self-improvement = frame); **no DSPy/no evolver** (ArcNet *shows* behavior; existing coding agents improve the fleet); Unplug = **source-trust monitoring** (trust per source, filter untrusted/scraped, flag forward-facing). New pillars: **agent-view** (machine-optimal twin of every datum) + **Time Machine** (counterfactual replay-from-trace, the headline). Landscape: nobody closes trace→fix→proof loop; CAR + GEPA validate feasibility. Concept in `08-vision-v2.md`.

**Whole plan unfolded to v2:** docs 00–06 revised (01 product, 02 arch with `replay.py` + agent-view API + Time Machine flow, 03 plan with replay harness Phase 4, 05 unplug=source-trust, 06 six-beat demo, 00 judging map). Added `09-frontend.md`.

**Frontend = Unplug design language** (dark terminal, pure black + electric cyan `#00e8ff`, monospace, sharp corners, CRT scanlines, `snake_case()` copy, `> arcnet` wordmark). Mock: `docs/mock/arcnet-v3.html` (Time Machine + human/agent toggle). Earlier mocks retired. `09-frontend.md` has the design system + IA + 4 copy-paste UI-generation prompts (cyan/amber/matrix/graphite).

**Consistency pass (v2):** unified dashboard name (Threats & Trust), explained F8/F12 numbering gaps, normalized "HQ"→"the UI" in prose (`hq/` stays the dir), verified P0/P1/P2 tiers match across 01/03, Signal schema identical, every demo beat maps to a P0 feature.

- **Next (Phase 0 in `03-plan.md`):** SigNoz Docker up, Agno hello trace, unplug smoke, replay feasibility spike, TabFM spike, service key + Query/metrics-list, submission form + deadline time.

## Day 1 — Tue Jul 21 (gap review + spec hardening, then build)

Full gap pass over the plan before coding. **Schedule re-anchored**: Mon went to concept, so build = Tue–Sat (Tue is a double day: foundations AM + shield core PM; TabFM spike and S2 moved to Wed). New specs: `10-time-machine.md` (recorded-transcript shape, tool-stub matching, precise diff semantics — `[EXPLOITED]` = model *attempted* the injected action, verdict schema, 12-incident corpus) and `11-scenarios.md` (per-scenario fixtures + telemetry assertions = the test suite; fleet clones L & O so a cut Agent K never leaves a fleet of one). Signals now have an **inline fast-path** (guard block → signal in ms; SigNoz alert = system of record) so "self-corrects in seconds" survives the alert-evaluation interval. Added **north star + success criteria + tradeoff order** to `08`, decision **gates G1–G5** to `03`, Beat-5 narration that preempts "didn't you already block it?". All Day-0/phase labels re-pointed to the new Day 1–6 calendar.

**Prove-pillar generalized (user call):** the Time Machine is no longer injection-centric — it diffs **whole behavior** (goal_reached/steps/tool_errors/cost core; resisted/exfil only for threat sessions). Market anchor added to `08`: model/prompt upgrades are swap-and-pray; replaying your own trace history = a behavioral regression suite. Beat 5 reworked: Worms loop replay live (killed→stops at step 5, −72% cost), Edgar pre-run second, corpus scorecard close. Corpus mix rebalanced problem-diverse (S4×3/S1×3/S5×2/S2×2/S0×2); S4 transcripts now mandatory; harness gains a step cap so a looping candidate terminates. **Deferred (user call):** deeper context-inspector work (step-by-step view of what each agent ingested) — parked as P1, build when time allows.

**Long-term commitment (user call):** ArcNet is a project we keep after the event — live real-work agents run under it and we use it ourselves. Consequences written into the docs: product-core vs demo-layer rules in `02` (core never imports scenario code; demo behavior = config + fixtures), "Beyond the hackathon" section in `08`, live-work dogfood agent added as P1 + a standing rule in `03`.

**Pacing switched to phase-gated (user call):** no calendar-day scheduling — six milestone-gated phases, each starting the moment the previous exit is green; the only hard date is the Sun Jul 26 submission. Hours banked early flow into Phase 5–6 polish/re-records. Added "The bar (the judge test)" to `03`: every phase exits demoable, hero views product-polished, nothing on camera depends on luck. All day labels across `00/02/04/05/06/07/10/11` converted to phase labels.
