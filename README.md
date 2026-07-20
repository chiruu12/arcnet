# ArcNet

**The shield for your AI agents.** Observability + active defense for AI-native systems, built on [SigNoz](https://signoz.io).

> *Protecting your stack from the scum of the universe.*

ArcNet watches every agent in your fleet — every LLM call, tool invocation, token spent — and doesn't just *show* you problems, it *acts* on them. When an agent gets prompt-injected, leaks PII, goes destructive, or spins into a runaway loop, ArcNet detects it (via [unplug-ai](https://pypi.org/project/unplug-ai/)), traces it (via OpenTelemetry → SigNoz), alerts on it (SigNoz alert rules), and **signals the agent's own loop to pause and self-correct** ([Agno](https://www.agno.com) guardrails + HITL + run cancellation).

Then it goes one step further: every incident becomes an exportable **Case File** — traces, detections, and timeline with embedded trace IDs — handed to a coding agent (Cursor, Claude Code) that investigates the live telemetry through the **SigNoz MCP server** and fixes the underlying agent.

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
| `hq/` | HQ dashboard — the MIB observation deck | React + Vite + Tailwind |
| `deploy/` | Self-hosted SigNoz + MCP server + provisioned dashboards & alerts | Docker Compose |
| `docs/` | Brief, product, architecture, plan, SigNoz + Unplug integration, Griffin, demo script, HQ mock | — |

## Status

Built for the **Agents of SigNoz** hackathon (WeMakeDevs × SigNoz, July 20–26 2026), Track 1: AI & Agent Observability.

Start with `docs/03-plan.md` for the build plan.
