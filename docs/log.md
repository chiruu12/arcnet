# Build log

## Day 0 — Mon Jul 20 (planning)

**v1 (initial):** docs 00–07 + first mock; framing = agent security + observability dashboard on SigNoz (Agno + unplug-ai + Griffin/TabFM + signals + Case File). Review pass fixed the calendar (Jul 20 = **Mon**, deadline **Sun Jul 26**), re-tiered so the demo rides on P0, rebalanced Phase 4, moved TabFM spike to Day 0 / seed.py to Phase 3, added S4 "Griffin-first" choreography, pinned the signal schema, enumerated the env surface. Deps verified installable.

**v2 pivot (office-hours + landscape):** reframed to **"agents that watch themselves and get better"** — the control plane for a self-improving fleet. Locked: unified spine (security = visceral demo, self-improvement = frame); **no DSPy/no evolver** (ArcNet *shows* behavior; existing coding agents improve the fleet); Unplug = **source-trust monitoring** (trust per source, filter untrusted/scraped, flag forward-facing). New pillars: **agent-view** (machine-optimal twin of every datum) + **Time Machine** (counterfactual replay-from-trace, the headline). Landscape: nobody closes trace→fix→proof loop; CAR + GEPA validate feasibility. Concept in `08-vision-v2.md`.

**Whole plan unfolded to v2:** docs 00–06 revised (01 product, 02 arch with `replay.py` + agent-view API + Time Machine flow, 03 plan with replay harness Phase 4, 05 unplug=source-trust, 06 six-beat demo, 00 judging map). Added `09-frontend.md`.

**Frontend = Unplug design language** (dark terminal, pure black + electric cyan `#00e8ff`, monospace, sharp corners, CRT scanlines, `snake_case()` copy, `> arcnet` wordmark). Mock: `docs/mock/arcnet-v3.html` (Time Machine + human/agent toggle). Earlier mocks retired. `09-frontend.md` has the design system + IA + 4 copy-paste UI-generation prompts (cyan/amber/matrix/graphite).

**Consistency pass (v2):** unified dashboard name (Threats & Trust), explained F8/F12 numbering gaps, normalized "HQ"→"the UI" in prose (`hq/` stays the dir), verified P0/P1/P2 tiers match across 01/03, Signal schema identical, every demo beat maps to a P0 feature.

- **Next (Phase 0 in `03-plan.md`):** SigNoz Docker up, Agno hello trace, unplug smoke, replay feasibility spike, TabFM spike, service key + Query/metrics-list, submission form + deadline time.
