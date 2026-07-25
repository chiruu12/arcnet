# What's left — ArcNet (as of 2026-07-25, submit Sun 2026-07-26)

Readiness pinned **~64% (cap ≤65)**. Suites on main: server **233** · agents **18** · sdk **81** · hq **97** · import boundaries clean.

Mechanical doc/test hygiene from the P11–P30 waves is **done** (HITL relay, corpus scorecard, prompt-swap UI, fleet latency, Griffin discovery, F9 canaries, context inspector, HQ deferrals, hero fixture, suite guards). What remains is **human ship work** plus a short list of genuinely open engineering items.

---

## A. Blocks submission — human only (nobody can do these for you)

| # | Item | State | Notes |
|---|------|-------|-------|
| A1 | **Publish the blog** | Draft ready, 135 lines, implementation-accurate | [`blog-draft.md`](blog-draft.md). Form requires a **NEW detailed implementation post**, not a repurposed one. Publish → copy URL. |
| A2 | **Record the video** | Script ready, shot-by-shot | [`video-script.md`](video-script.md). Target **< 3:00**, upload unlisted, verify it plays logged-out. **Use Edgar `s_ecfdb55d` for Shot 5**, not Worms (see §C1). |
| A3 | **README screenshots** | **4 slots still empty placeholders** | README §Screenshots is literally a "capture still pending" block with a numbered list. This is a **judged** surface — judges land on the README first. 10 minutes with the stack up. |
| A4 | **Submit the form** | Answers paste-ready | [`submission-form-answers.md`](submission-form-answers.md) → `https://forms.gle/xv1TXSiC54MEWujRA`. Required: YouTube link + blog link. Screenshot the confirmation. |
| A5 | **Rotate the SigNoz admin password** | Leaked into a session transcript | `.signoz-local-admin`. Localhost-only dev credential, but rotate it. Re-inject into `deploy/pours/deployment/compose.yaml` (gitignored) after. |

**Pre-flight before recording:** bring Docker + SigNoz up FIRST and confirm `docker ps` shows
`signoz-signoz-0 … (healthy)` **and** `/api/signoz/status` → `ui_reachable: true`. While the SigNoz
backend crash-loops, OTLP `:4318` still returns **200** and spans silently never reach ClickHouse —
a run in that window records to SQLite with **no trace to open on camera**.

---

## B. Genuinely open engineering (post-submission unless quota returns first)

| # | Item | Why it remains | Notes |
|---|------|----------------|-------|
| B1 | **Live hero replay re-verify** | OpenAI quota | Recorded G4 (`docs/_phase4_g4.json`) may be stale; rerun `scripts/phase4_g4_check.py` after top-up. |
| B2 | **G5 live MCP handoff** | Upstream stdio hang | HTTP/Query Range fallback ships (`read_models.py` hints, Case File zip). Live stdio MCP still **EXPLICIT DEFER** (`deploy/mcp/README.md`). |
| B3 | **Live-work dogfood agent** | Scenario + seed choreography | Agents J/L/O run scripted scenarios and seeded background rows — not continuous genuine production tasks. |
| B4 | **Input-layer detection gaps (9)** | Lives in **unplug-ai** (PyPI dep) | Paraphrased override, soft probing, persona framing, newline-split tokens, JSON role smuggling, multi-turn escalation, NL tool invocation, direct exfil questions, untainted `to`-field smuggling — corpus-locked in [`docs/33-guard-coverage.md`](../33-guard-coverage.md) §Known gaps. ArcNet consumes unplug-ai; it does not modify that package. |

---

## C. Honesty items to carry into the blog/video (decisions, not tasks)

**C1 — Worms replay is `mixed`, not a win.** Live: baseline `killed`/8 steps/**$0.00085** vs candidate
`partial`/7 steps/**$0.0109** — the candidate is **~12.8× more expensive** for one fewer step, and
`recommendation` reads *"review the mixed dimensions before changing routing."* Step count also moved
3 → 7 between runs. Edgar is the unambiguous hero (baseline `failed` → candidate `clean`). If you
show Worms at all, narrate it as *"mixed — cheaper isn't always better, and ArcNet says so."*

**C2 — Publishing 70.0%.** [`docs/33-guard-coverage.md`](../33-guard-coverage.md) measures 28/40 synthetic
payloads caught (70.0%). Recommendation: **publish it with the layered-defense framing.** The number alone
reads as "a third of injections get through," which is false — each payload is scanned at one
checkpoint in isolation, and 9 of 12 misses are input-only. Measured with a fresh guard per call, an
input-layer miss on retrieved content still **blocks at tool_call (0.85)**. The real story is that
**taint tracking, not regex, is the load-bearing defense** — which is the trust-boundary claim,
measured rather than asserted. That's a stronger blog paragraph than silence, and judges can run the
suite themselves.

**C3 — Readiness stays ~64.** P21–P30 were gap-closing and hardening. No new
user-facing capability tier, no closed live-check DEFER → no % move. Don't let a good week tempt a bump.

---

## Suggested order for today/tomorrow

1. **A5** rotate password
2. **A2** record while the stack is verified and warm
3. **A3** screenshots in the same sitting
4. **A1** publish blog (fold in C1 + C2 framing)
5. **A4** submit Sunday morning
6. **B1–B4** after the form is in (or when quota returns for B1)
