# ArcNet — Frontend (v2)

The v1 "ops console" mock is retired. ArcNet's UI adopts the **Unplug design language** (Unplug is the engine inside ArcNet, so they're one product family), executed at product grade. MIB survives only as wordmark + deadpan `snake_case()` copy.

Reference mock: `docs/mock/arcnet-v3.html` (Time Machine view, Unplug-styled).

## Design system (matched to Unplug)

**Aesthetic:** dark terminal / cyberpunk-lite. Pure-black canvas, one electric-cyan accent, monospace everything, hairline cyan borders, sharp corners, CRT scanline overlay, terminal chrome. Technical, credible, slightly ominous — a security-ops HUD for developers.

**Color tokens** (canonical = cyan):
```
--accent        #00e8ff   electric cyan (links, CTAs, active, "safe/allowed")
--accent-hover  #66f3ff
--accent-dim    rgba(0,232,255,.05)
--accent-border rgba(0,232,255,.18)
--accent-glow   rgba(0,232,255,.35)   (neon glow on primary button only)
--bg            #000000   page
--bg-surface    #050505   alt sections
--bg-elevated   #0a0a0a   cards
--bg-code       #020202   terminals / panels
--text          #b0b0b0   body
--text-2        #666666   secondary
--muted         #404040   comments / faint
--bright        #e0e0e0   headings (near-white, never pure white)
--danger        #ff3333   threat / blocked
--warn          #ffd93d   redacted / review
--ok            #34d399   resisted / clean   (or cyan for "allowed")
--border        rgba(0,232,255,.08–.14)  hairline, cyan-tinted
```
Chart/category palette: injection `#ff3333` · jailbreak `#a855f7` · data_leak `#ffd93d` · destructive `#60a5fa` · indirect `#34d399` · encoding `#fb923c`.

**Type:** monospace everywhere. Ship **JetBrains Mono** or **IBM Plex Mono** in the real app (self-host the woff2 — do NOT rely on a CDN). Weights: 700 headings/numbers, 500–600 labels/nav, 400 body. Big headlines with tight negative tracking (`-0.02em`); section eyebrows are `// UPPERCASE` at ~10px with wide positive tracking; table headers 9px uppercase. (Note: the artifact mock uses a mono *system stack* because the artifact CSP blocks font CDNs — the shipped app self-hosts the real face.)

**Shape & motif:** corners 2–4px (often square); 1px cyan-tinted hairline borders; no drop-shadows except the cyan glow on the primary button; `●` status dots + colored status text; macOS traffic-light dots on terminal panels; optional CRT scanline overlay + subtle binary-rain. Restrained, not loud.

**Copy voice:** lowercase, `snake_case()` / function-call style. `replay.run()`, `resisted_injection`, `[BLOCKED]`, `exit_code=0`, `hand_to(claude_code)`. Wordmark: `> arcnet` in cyan. Bracketed shouty status: `[EXPLOITED]`, `[RESISTED]`, `[OK]`.

## Information architecture

Sidebar split **observe / improve**:
- **observe:** `fleet_health` (agents + trust posture, forward-facing flagged, threats, cost, Griffin) · `signals` (live feed + HITL) · `sources_trust` (per-agent ingested-source ledger, what Unplug filtered/blocked)
- **improve:** `time_machine` (counterfactual replay — the hero) · `case_files` · `dashboards` (SigNoz deep-links)
- Global **`human_view ⇄ agent_view`** toggle in the top bar — every view flips to its agent-view JSON.

Hero screen = **Time Machine**: two-column baseline-vs-candidate replay diff + a terminal-style verdict readout + recommendation with `hand_to(claude_code)` / `replay_corpus()` actions. **The screen is incident-agnostic**: the same layout renders a loop/reliability replay (step lists = iterations; verdict rows = goal/steps/cost) or a threat replay (rows add resisted/exfil) — security is one lens, and the verdict panel only shows the dimensions the session has.

## UI-generation prompts (copy-paste into v0 / Lovable / Claude / etc.)

Four directions — all in the Unplug family, varying accent + intensity. Each is self-contained; generate, compare, pick. All target the **Time Machine** screen (the hero); swap the screen description to generate other views.

### Prompt A — Cyan terminal (canonical, matches Unplug)
```
Build a single dark dashboard screen for "ArcNet", an observability + security control plane for AI agent fleets. Screen: the "Time Machine" — a counterfactual replay that shows how two different LLMs handled the SAME recorded agent incident.

Aesthetic: dark terminal / cyberpunk-lite security HUD for developers. Pure black (#000) canvas, ONE electric-cyan accent (#00e8ff), MONOSPACE everywhere (JetBrains Mono / IBM Plex Mono). 1px cyan-tinted hairline borders (rgba(0,232,255,.12)), sharp 2–4px corners (mostly square), NO drop-shadows except a cyan neon glow on the primary button only. Subtle CRT scanline overlay. Near-white headings (#e0e0e0), mid-gray body (#b0b0b0), muted (#404040). Status colors: cyan/#34d399 = safe/resisted, #ffd93d = warn/redacted, #ff3333 = danger/blocked. Copy is lowercase snake_case function-call style ("replay.run()", "[BLOCKED]", "exit_code=0"). Wordmark "> arcnet" in cyan.

Layout: left sidebar (176px, on #020202) with "> arcnet" logo, nav grouped under "// observe" (fleet_health, signals, sources_trust) and "// improve" (time_machine [active, cyan left-border], case_files, dashboards), and a bottom mini fleet-status list. Top bar: breadcrumb "time_machine / replay_f3a9", a "demo" env tag, a segmented "human_view | agent_view" toggle, and a cyan "replay.run()" button with glow. Main: an eyebrow "// counterfactual_replay", H1 "would a different model have resisted the attack?", a one-line lede, then a control bar showing baseline chip [gpt-4o-mini · recorded] ⇄ candidate chip [claude-fable-5 · replay] + "tool_outputs=mocked" tag. Then a TWO-COLUMN diff: left "gpt-4o-mini [EXPLOITED]" (red-bordered), right "claude-fable-5 [RESISTED]" (green-bordered); each column lists 4 numbered steps (goal → fetch_url of an untrusted scraped page with a hidden injection → the divergence: left follows the injection and attempts an email exfil that gets [BLOCKED], right refuses and completes cleanly → outcome). Below, a terminal-style verdict panel (macOS traffic-light dots, title "replay.diff") printing a metrics table (goal_reached after_steer→clean, steps 9→6, cost/latency deltas, injection_resisted false→true, exfil_attempts 1→0, "exit_code=0"). Then a cyan-bordered recommendation box with action buttons "hand_to(claude_code)", "replay_corpus(n=12)".

Self-contained HTML+CSS (inline, no external requests). Dark only. Responsive: columns stack under 900px.
```

### Prompt B — Amber CRT (retro-terminal)
```
Same as Prompt A, but swap the accent to AMBER (#ffb000, hover #ffc94d, glow rgba(255,176,0,.35)) on a warmer near-black (#0a0806). Push the retro-CRT feel harder: stronger scanlines, a faint amber vignette, a blinking block cursor after headings, phosphor-glow on the accent. Keep danger #ff3333 and warn a softer amber. Everything else — monospace, sharp corners, snake_case copy, the Time Machine layout — stays identical. It should feel like an 80s amber terminal running a modern security tool.
```

### Prompt C — Matrix green
```
Same as Prompt A, but accent = MATRIX GREEN (#00ff41, dim rgba(0,255,65,.06)) on pure black. Add a subtle animated "binary rain" canvas behind the content at very low opacity (fake attack strings like "DROP TABLE users;", "ignore all prior instructions" that spawn and get a green "[blocked]" sweep). Keep the same layout, monospace, and snake_case copy. Danger stays #ff3333. Slightly more menacing/hacker mood than the cyan version.
```

### Prompt D — Refined graphite (enterprise-serious)
```
Same product and same Time Machine layout as Prompt A, but dial DOWN the neon for a more enterprise/credible feel: graphite grounds (#0b0d10 page, #12151c cards), softer cyan accent (#4cc4e0) used sparingly, keep monospace for all DATA/numbers/labels but allow a clean sans (Inter) for prose headings and lede. Drop the scanlines; keep 1px hairline borders but neutral-gray (#232a33) not cyan. Keep the terminal verdict panel and snake_case for code-like labels, but make body copy sentence-case. Should read like a serious observability product (Datadog/Honeycomb grade) that still has a terminal soul. Status colors: #35c46a ok, #d6a13a warn, #f2544b danger.
```

**How to use:** generate A first (it's the canonical Unplug match); if you want more punch try B/C; if it needs to read "serious enterprise tool" try D. To generate the other views, keep the design-system paragraph and replace the layout paragraph with: *fleet_health* (a grid of agent cards with trust posture + forward-facing flags + a threats/cost/anomaly strip), *sources_trust* (a dense mono table of ingested sources with trust levels and Unplug verdicts), or *signals* (a live feed with steer/kill/pause rows and HITL approve/reject).
