# ArcNet

**The control plane for a self-improving agent fleet.** Observability + active defense for AI-native systems, built on [SigNoz](https://signoz.io).

> *Agents that watch themselves — and get better.*

ArcNet watches every agent in your fleet — its behavior, its cost, and **the trust of everything it ingests**. Attacks come in through untrusted sources (scraped pages, tool outputs), so [unplug-ai](https://pypi.org/project/unplug-ai/) tags every source's trust level, filters the untrusted ones before they reach the model, and flags forward-facing agents as higher-risk. When something slips through, ArcNet traces it (OpenTelemetry → SigNoz), alerts on it, and **signals the agent to self-correct** ([Agno](https://www.agno.com) guardrails + run cancellation).

Then the two things nobody else has:
- **Agent-view** — every datum has a machine-optimal twin, so the coding agents you already run (Claude Code, Codex, Cursor) can read the fleet's health and incidents in *their* format and improve the agents.
- **The Time Machine** — replay a recorded incident against a different model or prompt (tool outputs mocked from the trace) and *prove* it would behave better: goal reached, fewer steps, lower cost, attack resisted. Your trace history becomes a behavioral regression suite — the answer to "can we upgrade the model?" that isn't swap-and-pray.

See `docs/08-vision-v2.md` for the full concept and `docs/mock/arcnet-v3.html` for the UI.

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
| `docs/` | Brief, product, architecture, plan, SigNoz + Unplug integration, demo script, Griffin spec, vision-v2, frontend + UI prompts, Time Machine spec, Bug Suite spec, mocks | — |

## Status

Built for the **Agents of SigNoz** hackathon (WeMakeDevs × SigNoz, July 20–26 2026), Track 1: AI & Agent Observability.

Start with `docs/03-plan.md` for the build plan.
