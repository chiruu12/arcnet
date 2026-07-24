# What's left — ArcNet (as of 2026-07-25, submit Sun 2026-07-26)

Main is `579b540`. Suites: server **219** · agents **18** · sdk **63** · hq **60** · boundaries clean · coherence exit 0.
Readiness pinned **~64% (cap ≤65)**. Demo stack verified live today — see [`capture-checklist.md`](capture-checklist.md) Rehearsal 2.

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

## B. Blocks submission — mechanical (fast, low risk, delegable)

| # | Item | Why it matters | Risk |
|---|------|----------------|------|
| B1 | **README verification commands miss 49 tests** | README §Verification says `uv run python -m unittest discover -s sdk/tests`. The P14 corpus suite is **pytest-style**, so unittest discovers **14** tests where pytest finds **63**. A judge following the README sees a fraction of the suite and may conclude the repo is thinly tested. | Low — doc fix + add the pytest command |
| B2 | **`uv run` in README prunes the env** | `uv run` re-syncs workspace members and prunes `tabfm`/`torch`/`pytest`. A judge running README commands in order can end up with a different env than the one that passes. | Low — document `uv sync --all-packages --all-groups && uv pip install pytest` |
| B3 | **`docs/20-honest-progress.md` cites stale suite counts** | Row 11 still reads "server 130 / agents 17 / sdk 6 / hq 26" against actual 219/18/63/60. The honesty doc being stale is a bad look **precisely because** honesty is the project's stated posture. | Low — numbers only, no % move |
| B4 | **`docs/33` not linked from README or `docs/20`** | The measured guard-coverage report is arguably the most credible artifact in the repo and nothing points at it. | Low |
| B5 | **Cold-clone reproducibility unverified** | README claims judges reproduce with `docker compose up` + one script. Never tested from a *fresh* clone since the hardening waves. | Medium — may surface real breakage |

---

## C. Honesty items to carry into the blog/video (decisions, not tasks)

**C1 — Worms replay is `mixed`, not a win.** Live: baseline `killed`/8 steps/**$0.00085** vs candidate
`partial`/7 steps/**$0.0109** — the candidate is **~12.8× more expensive** for one fewer step, and
`recommendation` reads *"review the mixed dimensions before changing routing."* Step count also moved
3 → 7 between runs. Edgar is the unambiguous hero (baseline `failed` → candidate `clean`). If you
show Worms at all, narrate it as *"mixed — cheaper isn't always better, and ArcNet says so."*

**C2 — Publishing 65.8%.** [`docs/33-guard-coverage.md`](../33-guard-coverage.md) measures 25/38 synthetic
payloads caught. Recommendation: **publish it with the layered-defense framing.** The number alone
reads as "a third of injections get through," which is false — each payload is scanned at one
checkpoint in isolation, and 9 of 13 misses are input-only. Measured with a fresh guard per call, an
input-layer miss on retrieved content still **blocks at tool_call (0.85)**. The real story is that
**taint tracking, not regex, is the load-bearing defense** — which is the trust-boundary claim,
measured rather than asserted. That's a stronger blog paragraph than silence, and judges can run the
suite themselves.

**C3 — Readiness stays ~64.** P11–P14 were hardening, resilience, and measurement. No new
user-facing capability, no closed live-check DEFER → no % move. Don't let a good week tempt a bump.

---

## D. Post-submission engineering (real work, do NOT start before recording)

| # | Item | Value |
|---|------|-------|
| D1 | **Close the untainted-exfil hole** | P14's one genuine end-to-end gap: untainted content leaving via a tool side effect is `allow`/**0.0** at `tool_call`. Output scanning catches the same content (`email_address` 0.8, raw SSN 0.8) and the tainted variant blocks at 0.85 — but a side effect doesn't necessarily pass through output scanning. So user-origin secrets, or any taint-provenance miss, get out. **Highest-value security work remaining.** |
| D2 | **Input-layer detection gaps (9)** | Paraphrased override, soft prompt-extraction probing, simulation/authority persona framing, newline-split tokens, JSON role smuggling, soft + session-spanning multi-turn escalation, NL tool invocation, direct exfil questions. All corpus-locked in `docs/33` §Known gaps. |
| D3 | **HQ deferrals from P13** | Per-view retry buttons, agent-view schema validation, SSE "stream offline" indicator, case-file download error handling, browser E2E white-screen regression suite. |
| D4 | **P6-C corpus scorecard** | Standing explicit DEFER — no server endpoint. Either build `POST /api/replay/corpus` or keep the DEFER honest. |
| D5 | **PydanticAI / PI agents spike** | Your own parked question: prove a PydanticAI agent emits 1 trace + 1 guard verdict through the existing SDK contract. ArcNet is Agno-only today (`UnplugGuardrail` binds `agno.guardrails.BaseGuardrail`); telemetry/Time Machine/server/HQ are already framework-neutral. |
| D6 | **Live MCP handoff (G5)** | Long-standing DEFER — hand a Case File to Claude Code with SigNoz MCP connected, record the backup beat. |

---

## Suggested order for today/tomorrow

1. **B1–B4** (30 min, delegable now — doesn't touch the demo path)
2. **A5** rotate password
3. **A2** record while the stack is verified and warm
4. **A3** screenshots in the same sitting
5. **A1** publish blog (fold in C1 + C2 framing)
6. **A4** submit Sunday morning
7. Everything in **D** after the form is in
