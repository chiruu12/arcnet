# ArcNet — Product

## One-liner

**ArcNet is the defense shield for AI agent fleets**: full observability into what your agents are doing (SigNoz), real-time detection of what's going wrong (unplug-ai), active signals that let the agent's own loop pause and self-correct, and exportable Case Files that let your coding agent fix the root cause.

## Why this matters

Everyone traces agents. Almost nobody **closes the loop**. Today's agent observability answers "what happened?"; ArcNet also answers "what do we do about it — *right now, automatically*?" and "how do we make sure it never happens again?".

Three loops, increasing time horizon:

1. **Inline (ms)** — guard middleware scans inputs/outputs/tool-calls; blocks or redacts before damage. Telemetry emitted either way.
2. **Reactive (seconds)** — SigNoz alert rules watch fleet-level patterns (threat spikes, cost burn, loop depth, latency); alerts hit our webhook; ArcNet converts them to **signals**; the agent framework's own hooks (Agno guardrails, HITL pause/approve, run cancellation) pause/steer/kill the run.
3. **Corrective (minutes)** — one click exports the incident as a **Case File**: trace tree + findings + timeline + suggested-fix prompt, formatted for a coding agent. The coding agent (Cursor/Claude Code) connects to the **SigNoz MCP server**, pulls the live trace evidence itself, and patches the agent's prompt/tools. The observability platform becomes an input to development.

## Men in Black theme

The MIB conceit is load-bearing, not paint. MIB is *literally* an agency that monitors a registry of aliens living among us and neutralizes threats without civilians noticing.

| MIB | ArcNet |
|---|---|
| The ArcNet shield (MIB 3 — deployed on Apollo 11 to stop the Boglodite invasion) | The platform itself: a shield you deploy around your fleet |
| MIB HQ observation wall | `hq/` dashboard — live fleet board |
| Registered aliens living on Earth | Your agents, registered + continuously monitored |
| Edgar — a bug in a human suit | A prompt-injected agent: looks normal, acts hostile. Our attack suite = **the Bug Suite** |
| The Neuralyzer | Redaction: PII/secrets flash-wiped from outputs (with the flash animation) |
| Case files | Exportable incident bundles |
| Griffin — sees all possible futures, notices when reality deviates | FM-powered anomaly detection: forecasts each metric's expected band, reports only true outliers |
| Agents J & K | The demo agents |
| "Protecting the Earth from the scum of the universe" | "Protecting your stack from the scum of the universe" |

Visual language (for `hq/`): black/white monochrome, sharp suits aesthetic — white type on near-black, one accent (alert red), clean sans + mono for telemetry, subtle scanline/CRT texture on the fleet board, neuralyzer white-flash micro-animation on redaction events. The deck is dark-only by design ("sunglasses on") — the shades control is deadpan set-dressing, not a real light mode. Keep it restrained — MIB is deadpan, not campy. **Reference implementation: `docs/mock/hq.html`.**

## Features (scored scope)

Feature IDs are stable labels (assigned in build order, not priority order); the tier is what matters. Every P0 item carries a demo beat — see the cut list in `03-plan.md`. (F12 was a standalone SigNoz-MCP feature, now folded into F7 — numbering skips it.)

**P0 — demo-critical, must land**
- F1. **Instrumented fleet**: Agno demo agents (on AgentOS) fully traced to self-hosted SigNoz (LLM calls, tool calls, tokens, cost, errors) via `openinference-instrumentation-agno`; prebuilt Agno dashboard template imported.
- F2. **Guard telemetry**: every unplug-ai scan emitted as spans/events/metrics — threats are first-class telemetry (`arcnet.guard.*`). Implemented as an idiomatic Agno guardrail (`UnplugGuardrail`) + tool hooks.
- F3. **The Bug Suite**: scripted attack scenarios (baseline, indirect injection/exfil, PII leak, destructive tool call, jailbreak, runaway loop) runnable on demand.
- F4. **SigNoz depth**: provisioned dashboards + alert rules (incl. native seasonal anomaly) + webhook channel (see `04-signoz-integration.md`).
- F5. **Signals**: SigNoz alert → webhook → signal bus → Agno hooks (`steer` / `kill`) → agent self-corrects. The headline moment.
- F6. **HQ dashboard**: MIB observation deck — fleet board, live threat feed, Griffin card, signals log.
- F7. **Case File export + SigNoz MCP handoff**: incident bundle (traces via Query API + findings + timeline + fix-prompt + embedded trace_ids) as markdown/JSON; the coding agent pulls live evidence via the SigNoz MCP server and fixes the agent. (MCP server also used dev-time with SigNoz agent skills.)
- F8. **Neuralyzer**: redaction events surfaced in HQ with the flash; before/after view.
- F13. **Griffin core**: foundation-model anomaly detection on agent metrics (Google TabFM, zero-shot + conformal bands) — reports only true outliers, silent on normal data. Full design: `07-griffin-anomaly.md`.

**P1 — strong, build if P0 done**
- Native SigNoz seasonal anomaly alert (the pairing story: seasonal needs history, Griffin covers new agents from minute one).
- Griffin breadth: metric auto-discovery + top-N series.
- F9. **Canary tokens**: register a system-prompt canary (`guard.add_canary`, verify Day 0); prove system-prompt exfiltration detection.
- HITL pause beat: the `pause` signal → Agno HITL approve/reject from HQ (the flow is built; this makes it a demo beat).
- HQ Session Detail: full timeline drill-down (else deep-links into SigNoz UI).

**P2 — stretch, cut freely**
- F10. LLM judge for borderline verdicts (unplug `CallableJudge` + cheap model).
- F11. Second framework adapter (OpenAI Agents SDK) proving the SDK is framework-agnostic.
- Agent K (second fleet member; J alone is a complete story).

## Demo story (short version — full script in 06)

1. HQ board: fleet of agents, all green, telemetry flowing. ("Every agent on Earth, registered and monitored.")
2. Run the Bug Suite. Agent J fetches a webpage with a hidden injection → tries to exfiltrate via email.
3. Split screen: SigNoz trace shows the poisoned span; guard blocks the tool call; alert fires; **a `steer` signal lands in Agent J's loop — it announces the fetched content was hostile, quarantines it, and completes the task safely without stopping for a human** (fully autonomous self-correction; the `pause`/HITL path is a separate signal kind, shown elsewhere).
4. PII scenario → neuralyzer flash → redacted output; runaway loop → cost alert → kill signal.
5. Export the Case File → Cursor (SigNoz MCP connected) reads it, pulls the trace itself, identifies the vulnerable tool prompt, proposes the fix.
6. Close on the SigNoz dashboards: every detection, token, and dollar accounted for.
