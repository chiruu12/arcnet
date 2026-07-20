# ArcNet

**The control plane for a self-improving agent fleet.** Observability + active defense for AI-native systems, built on [SigNoz](https://signoz.io).

> *Agents that watch themselves — and get better.*

ArcNet watches every agent in your fleet — its behavior, its cost, and **the trust of everything it ingests**. Attacks come in through untrusted sources (scraped pages, tool outputs), so [unplug-ai](https://pypi.org/project/unplug-ai/) tags every source's trust level, filters the untrusted ones before they reach the model, and flags forward-facing agents as higher-risk. When something slips through, ArcNet traces it (OpenTelemetry → SigNoz), alerts on it, and **signals the agent to self-correct** ([Agno](https://www.agno.com) guardrails + run cancellation).

Then the two pillars nobody else builds at the **agent-session** level:
- **Agent-view** — every datum has a machine-optimal twin, so the coding agents you already run (Claude Code, Codex, Cursor) can read the fleet's health and incidents in *their* format and improve the agents.
- **The Time Machine** — replay a recorded incident against a different model or prompt (tool outputs mocked from the trace) and *prove* it would behave better: goal reached, fewer steps, lower cost, attack resisted. Your trace history becomes a behavioral regression suite — the answer to "can we upgrade the model?" that isn't swap-and-pray. (LangSmith and Braintrust replay a *call* or a dataset example against a new model; ArcNet replays the **whole recorded agent session** — goal, tools, and trust checks live.)

See `docs/08-vision-v2.md` for the full concept and `docs/mock/arcnet-v3.html` for the UI.

## Provenance disclosure

[unplug-ai](https://pypi.org/project/unplug-ai/) is a separate open-source library (Apache-2.0) by the same author, published before this event and consumed here as infrastructure — like Agno or FastAPI, with one honest difference: we wrote it too. Nothing from unplug-ai's implementation is part of what's being judged. Everything judged — the fleet observability, signals, agent-view, Time Machine, and the SigNoz integration — is written during the event, on top of it.

## The loop

```
agent runs → OTel telemetry → SigNoz → alert fires → webhook → ArcNet signal
    ↑                                                              │
    └──────────── agent pauses / self-corrects / is quarantined ◄──┘
```

## Components

| Dir | What | Stack |
|---|---|---|
| `sdk/` | Instrumentation + UnplugGuardrail + signal client | Python, OTel, unplug-ai |
| `agents/` | Demo agents (J & K) + the Bug Suite attack scenarios | Agno / AgentOS |
| `server/` | Signal bus, SigNoz query proxy, Case File exporter | FastAPI |
| `hq/` | ArcNet UI — Fleet Health · Time Machine · Sources & Trust | React + Vite + Tailwind |
| `deploy/` | Self-hosted SigNoz + MCP server + provisioned dashboards & alerts | Docker Compose |
| `docs/` | Brief, product, architecture, plan, SigNoz + Unplug integration, demo script, Griffin spec, vision-v2, frontend + UI prompts, Time Machine spec, Bug Suite spec, data & API contract, mocks | — |

## Status

Built for the **Agents of SigNoz** hackathon (WeMakeDevs × SigNoz, July 20–26 2026), Track 1: AI & Agent Observability.

**Phase 0 foundations are up:** repo scaffold, SigNoz `v0.133.0` via Foundry, hello Agno traces with real OpenInference attrs recorded in `docs/04`, unplug S1 taint proven, replay+steer G1 green. Start with `docs/03-plan.md` for the build plan.

## Quick start (local)

```bash
# 1. Env
cp .env.example .env   # fill OPENAI_API_KEY (and optional ANTHROPIC_API_KEY)

# 2. Python workspace
uv sync --all-packages

# 3. SigNoz (pinned v0.133.0) — needs Docker Desktop ≥4 GiB
#    Install foundryctl once: https://github.com/SigNoz/foundry/releases
cd deploy && foundryctl cast -f casting.yaml && cd ..
# UI: http://localhost:8080  · OTLP HTTP: localhost:4318

# 4. One manual step (cannot be scripted headlessly):
#    SigNoz UI → Settings → Service Accounts → New → Keys → Add Key
#    Paste into .env as SIGNOZ_API_KEY=…
#    (Query Range API uses header SIGNOZ-API-KEY)

# 5. HQ shell
cd hq && pnpm install && pnpm dev
```

Spikes used in Phase 0 live under `scripts/phase0_*.py` (hello trace, replay+steer, oversized fixture).

