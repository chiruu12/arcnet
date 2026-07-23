# ArcNet

**Make your agents work properly — and enhance them.** Observability + active defense for AI-native systems, built on [SigNoz](https://signoz.io).

> *Agents that watch themselves — and get better.*

ArcNet is the enhancement layer for agent fleets: it watches behavior, cost, and **the trust of everything an agent ingests**. Attacks come in through untrusted sources (scraped pages, tool outputs), so [unplug-ai](https://pypi.org/project/unplug-ai/) tags every source's trust level, filters the untrusted ones before they reach the model, and flags forward-facing agents as higher-risk. When something slips through, ArcNet traces it (OpenTelemetry → SigNoz), alerts on it, and **signals the agent to self-correct** ([Agno](https://www.agno.com) guardrails + run cancellation).

Then the two pillars that close the improve loop at the **agent-session** level:

- **Agent-view** — every datum has a machine-optimal twin (`GET /api/agent-view/{view}/{id}`), so the coding agents you already run (Claude Code, Codex, Cursor) can read fleet health, signals, and incidents in *their* format and improve the agents.
- **The Time Machine** — replay a recorded incident against a different model or prompt (tool outputs mocked from the transcript, **same guardrail**) and *prove* it would behave better: goal reached, fewer steps, lower cost, attack resisted. Your trace history becomes a behavioral regression suite — the answer to "can we upgrade the model?" that isn't swap-and-pray. (LangSmith and Braintrust replay a *call* or a dataset example against a new model; ArcNet replays the **whole recorded agent session** — goal, tools, and trust checks live.)

**Product overview (start here):** [`docs/23-product-overview.md`](docs/23-product-overview.md) — what ArcNet is/isn’t, core loop, shipped vs deferred, HQ view evolution, honesty **~57% / ≤60%**. **Measurement / roadmap source of truth:** [`docs/20-honest-progress.md`](docs/20-honest-progress.md) · [`docs/21-next-phases-plan.md`](docs/21-next-phases-plan.md) · [`docs/22-next-agent-packets.md`](docs/22-next-agent-packets.md). Usage guide: [`docs/14-product-guide.md`](docs/14-product-guide.md). Productization: [`docs/17-product-rework-plan.md`](docs/17-product-rework-plan.md). Concept: `docs/08-vision-v2.md`. Demo narration: `docs/06-demo-script.md`.

## Provenance disclosure

[unplug-ai](https://pypi.org/project/unplug-ai/) is a separate open-source library (Apache-2.0) by the same author, published before this event and consumed here as infrastructure — like Agno or FastAPI, with one honest difference: we wrote it too. Nothing from unplug-ai's implementation is part of what's being judged. Everything judged — the fleet observability, signals, agent-view, Time Machine, and the SigNoz integration — is written during the event, on top of it.

## The loop

```
agent runs → OTel telemetry → SigNoz → alert fires → webhook → ArcNet signal
    ↑                                                              │
    └──────────── agent pauses / self-corrects / is quarantined ◄──┘
```

## Two hero incidents (real, measured, 3-run stable)

Both hero replays are **live model runs, verified stable across 3× replay** (`scripts/phase4_g4_check.py` → `docs/_phase4_g4.json`). Verdicts are honest: security/reliability wins are surfaced *with* their cost tradeoffs, never as fake "improved".

| | S1 "Edgar" — indirect injection | S4 "Worms" — runaway loop |
|---|---|---|
| baseline (`gpt-4o-mini`, recorded) | follows a poisoned page's social-engineering, attempts `send_email` exfil → **blocked by taint guard** at the tool-call checkpoint | paginates forever, token burn flagged by Griffin → **killed** |
| candidate (`gpt-4o`, replayed) | **resists the injection 3/3**, answers the shipping question (`exfil 0 vs 1`) | **breaks the loop itself** (6 paginate calls vs 8, no kill needed) |
| verdict | `mixed` — security improved, ~10× cost | `mixed` — reliability improved, higher cost |

## Components

| Dir | What | Stack |
|---|---|---|
| `sdk/` | Instrumentation + UnplugGuardrail + signal client + replay harness | Python, OTel, unplug-ai |
| `agents/` | Agent J + the Bug Suite attack scenarios + replay runtime | Agno / AgentOS |
| `server/` | Signal bus (SSE), Time Machine, agent-view, Case File exporter, Griffin anomaly watcher, SigNoz webhook | FastAPI, SQLite |
| `hq/` | ArcNet UI — fleet_health · signals · sources_trust · time_machine · case_files · dashboards, with a global `human_view ⇄ agent_view` toggle | React + Vite |
| `deploy/` | Self-hosted SigNoz + MCP server + provisioned dashboards & alerts | Docker Compose |
| `docs/` | Product, architecture, plan, integrations, Time Machine + Bug Suite specs, data & API contract, product map, review brief, build log | — |

## Quick start

```bash
# 1. Env
cp .env.example .env         # fill OPENAI_API_KEY

# 2. Python + JS workspaces
uv sync --all-packages
cd hq && pnpm install && cd ..

# 3. Bring up local stack (SQLite-primary — no Docker required)
./scripts/run-demo.sh
# → HQ UI    http://localhost:5173
# → API      http://127.0.0.1:8000/api/fleet
```

`run-demo.sh` seeds Griffin baselines and a sample fleet, starts the ArcNet server and the agent replay runtime, then serves HQ. Recorded hero incidents ship in history; hit `replay.run()` in the Time Machine (needs `OPENAI_API_KEY`) to re-derive a counterfactual live, or export any incident as a Case File.

### Optional: SigNoz depth (Docker)

```bash
# SigNoz pinned v0.133.0 — needs Docker Desktop ≥4 GiB
cd deploy && foundryctl cast -f casting.yaml && cd ..
# UI http://localhost:8080 · OTLP http://localhost:4318
# Then: SigNoz UI → Settings → Service Accounts → key → .env SIGNOZ_API_KEY=…
python deploy/provision/setup.py     # dashboards + v5 alert rules
./deploy/mcp/install.sh              # SigNoz MCP for the Case File beat
```

## Architecture & model boundaries

```
agents (AgentOS sample fleet) ──▶ sdk (arcnet: OTel + UnplugGuardrail + signals + replay harness)
        │                              │ OTLP
        │ POST /api/*                  ▼
        └────────▶ server (FastAPI + SQLite) ◀──── SigNoz webhook (optional)
                    │  repository → read models → thin routes
                    ├─ human APIs  → hq (React)
                    └─ agent APIs  → /api/agent-view/* + Case File → coding agents
```

- **Human vs agent read models** — one repository module owns every query; two serializer
  layers project the same records for two audiences. Dashboards get stable typed rows and
  health aggregates; coding agents get bounded, evidence-dense context (causal timeline, guard
  verdicts, IDs, digests, MCP hints) — never full tool outputs or secrets.
- **Unplug runs in-process** in the SDK: a CPU-only synchronous guard with per-session taint
  state. No network hop in the fail-closed path.
- **Griffin** (anomaly watcher) runs a **MAD** statistical baseline in-process today.
  **TabFM is required** on Phase 7 (`google/tabfm-1.0.0-pytorch`, `subfolder="regression"`)
  with MAD as the runtime degrade path — **not live yet**. TabPFN is deferred/out.
- **No vLLM** — replay compares hosted chat models, so the provider API is the inference
  boundary.
- **Import rule**: `sdk/`, `server/`, `hq/` never import `agents/` or `scripts/`
  (enforced by `scripts/check_import_boundaries.py`).

## The Case File handoff

Every incident exports as a zip (`GET /export/case-file/{session_id}`) containing:

- `case-file.md` — root cause (guard checkpoint, trust level, category, evidence), timeline, recommended actions, and a **fix-prompt preamble** for a coding agent, with SigNoz MCP instructions embedded.
- `case-file.json` — the same incident as the machine-optimal agent-view envelope.

Hand it to Claude Code with the SigNoz MCP connected and it pulls the traces and proposes the fix — closing the loop from *observed incident* to *improved agent*.

## Screenshots

> Human capture still pending (SigNoz stack + provision are available — see `docs/14-product-guide.md` §10). Slots:
>
> 1. Fleet Health — trust posture across the fleet, forward-facing flagged
> 2. Time Machine — Edgar baseline `[EXPLOITED]` vs candidate `[RESISTED]` with the verdict terminal
> 3. SigNoz fleet dashboard · threat center (ClickHouse SQL panel with the query visible) · reliability board
> 4. Seasonal-anomaly alert rule next to Griffin's MAD card

## Verification

```bash
# Python (sdk + server + agents fixture contract)
PYTHONPATH="sdk:server" uv run python -m unittest discover -s sdk/tests
PYTHONPATH="sdk:server" uv run python -m unittest discover -s server/tests
PYTHONPATH="sdk:agents" uv run python -m unittest agents.tests.test_s1_fixture

# Boundaries + lockfile
uv run python scripts/check_import_boundaries.py
uv run python scripts/tests/test_check_import_boundaries.py
uv lock --check

# Frontend
cd hq && pnpm build

# Hero replay stability gate (needs OPENAI_API_KEY + running services)
uv run python scripts/phase4_g4_check.py
```

## Judging criteria map

| Criterion | Where to look |
|---|---|
| Potential Impact | trace→fix→proof loop: observe → block/steer → Case File → Time Machine proof. Source-trust targets OWASP LLM01 (injection). |
| Creativity & Innovation | Time Machine (whole-session counterfactual replay, guard live) + agent-view (machine twin of every panel). Prior art named honestly: LangSmith/Braintrust replay calls/datasets, not sessions. |
| Technical Excellence | OpenInference semconv (real emitted keys), repository → read models → thin routes, idiomatic Agno guardrails/hooks, SQLite-primary replay, tests in `sdk/tests` + `server/tests`. |
| Best Use of SigNoz | OTLP traces/metrics/logs, 3 provisioned dashboards + v5 alert rules + webhook → signal bus, SigNoz MCP in the Case File handoff (`deploy/`). |
| User Experience | Six-view HQ, cascading agent→model→session pickers, `human_view ⇄ agent_view` toggle, local bring-up script. |
| Presentation Quality | `docs/06-demo-script.md`, this README, `docs/02-architecture.md` diagrams. |

## Limitations (honest)

- **No auth** — localhost surface by design; not auth theater.
- **SQLite-primary local path is the default** (`./scripts/run-demo.sh`). SigNoz (Docker) is optional
  depth: dashboards/alerts provision when a service-account key is present; live MCP stdio
  handoff remains PARTIAL. README screenshots and the submission video are still human tasks
  (`docs/14-product-guide.md` §10).
- **Griffin = MAD** until Phase 7 TabFM exits; never claim TabFM/TabPFN live in HQ/README.
  TabFM required on roadmap; TabPFN deferred. See [`docs/20`](docs/20-honest-progress.md) /
  [`docs/21`](docs/21-next-phases-plan.md).
- **HITL decide** updates SQLite today — not a live AgentOS pause relay yet (Phase 6).
- **Apply `confirm: true`** is a human gate, not auth. **SigNoz MCP** remains PARTIAL.
- **Live AgentOS restart** after apply is an operator step (`agentos_reload_required` + probe);
  auto-restart is unproven / out of scope for now.
- Overall readiness **~57% / ≤60%** — no 74/80/95 theater ([`docs/20`](docs/20-honest-progress.md)).
- Temp-0 replay is variance reduction, not determinism — hence the 3-run majority and the
  honest `inconclusive` verdict.
- APIs return epoch-millisecond timestamps (documented drift from `docs/12`'s ISO-8601 note;
  a versioned post-v1 API converts).
- Product overview: [`docs/23-product-overview.md`](docs/23-product-overview.md).
- Full usage + HQ audit: [`docs/14-product-guide.md`](docs/14-product-guide.md).
- Productization: [`docs/17-product-rework-plan.md`](docs/17-product-rework-plan.md).
- Next phases + packets: [`docs/21`](docs/21-next-phases-plan.md) · [`docs/22`](docs/22-next-agent-packets.md).

## Status

Built for the **Agents of SigNoz** hackathon (WeMakeDevs × SigNoz, July 20–26 2026), Track 1: AI & Agent Observability — and kept as a real product after the event. Build log: `docs/log.md`.

Licensed under [Apache-2.0](LICENSE). unplug-ai provenance disclosure above.
