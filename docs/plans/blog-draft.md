# Building ArcNet: session-level agent observability and counterfactual replay on SigNoz

> DRAFT for the Agents of SigNoz submission (project blog link). Publish on dev.to / Hashnode /
> personal site, then paste the URL into the form. Everything below is implementation-accurate as
> of the submission commit; edit voice/length freely, keep the numbers honest.

AI agents fail in ways dashboards weren't built for. A support agent scrapes a page with a hidden
instruction and quietly tries to email your customer table. A batch agent hits an endless
pagination loop and burns tokens for nineteen steps before anyone notices. And when you finally
want to fix one — swap the model, tighten the prompt — the honest answer to "will it behave
better?" is usually a shrug.

ArcNet is my attempt to close that loop on top of [SigNoz](https://signoz.io): observe the fleet,
defend the trust boundary, and then **prove** an upgrade by replaying real recorded incidents
against the candidate. This post is the implementation tour: what I actually wired into SigNoz,
what worked, and what I'd tell you before you build the same thing.

## The shape of the system

```
Agno agents (+ unplug guardrails)          React HQ ("mission control")
        │  OpenTelemetry (OpenInference)          │
        ▼                                         ▼
   SigNoz (self-hosted) ◄──── webhooks ────► ArcNet server (FastAPI + SQLite)
        │   dashboards · alerts · traces          │  signals · threats · replays · case files
        └────────── Query Range API ──────────────┘
```

Demo agents run on Agno's AgentOS. Every agent is wrapped by
[unplug-ai](https://pypi.org/project/unplug-ai/) guardrails at four checkpoints — input,
retrieved content, tool call, output — so every ingested source gets a trust level and every
guard verdict (rule, pattern class, risk score) becomes structured telemetry instead of a
boolean. The ArcNet server keeps the system-of-record in SQLite; SigNoz keeps the traces,
dashboards, and alerting.

## How SigNoz is wired in (the part you came for)

**Self-hosted, via Docker.** The whole stack runs locally: SigNoz UI on `:8080`, OTLP ingest on
the standard ports, provisioned with a service-account API key.

**OpenInference semconv, not `gen_ai.*`.** I instrumented Agno with
`openinference-instrumentation-agno`. One thing worth knowing before you build: the span names
you get are OpenInference-style — `{agent}.run → {model}.invoke → {tool}` — and the attributes
follow OpenInference semconv, *not* the OTel `gen_ai.*` conventions. Every dashboard query and
alert below is written against what the instrumentor actually emits, which I verified span by
span before writing a single panel.

**Custom `arcnet.*` span attributes.** On top of the standard spans, the SDK emits guard
telemetry: `arcnet.guard.checkpoint`, `arcnet.guard.action`, `arcnet.guard.risk_score`,
`arcnet.guard.top_category`, and — after the hardening pass — `arcnet.guard.rule` and
`arcnet.guard.pattern_class`. A blocked exfiltration isn't a log line; it's a span you can
aggregate, alert on, and join back to the session.

**Four dashboards.** Fleet Ops (sessions, latency, cost per agent), Threats & Trust (guard
actions by category — including a ClickHouse SQL panel for the join SigNoz's builder can't
express), Cost & Tokens, and the prebuilt Agno dashboard template. The ClickHouse panel was a
pleasant surprise: when the query builder ran out, raw SQL over the traces table kept going.

**Alerts on the v5 payload.** Six alert rules fire on threat spikes, cost runaway, token-rate
anomalies. Two implementation notes that cost me real time: the alert API wants the v5
`queries` payload shape (legacy payloads are rejected), and SigNoz's native **seasonal anomaly
rule** needs days of history and ≥5-minute evaluation windows — great for mature fleets, silent
on a brand-new agent. That gap is why ArcNet ships its own statistical baseline (below).

**Webhook → signal → self-correction.** Alerts POST to `/webhooks/signoz` on the ArcNet server,
which converts them into **signals** — steer, kill, pause — delivered to the running agent via
Agno's guardrail hooks and run cancellation. Guard blocks also emit an inline fast-path signal
in milliseconds, so "the agent corrected itself in seconds" is honest on camera; the SigNoz
alert lands right behind it as the system of record.

**Query Range API for evidence.** Case files don't screenshot dashboards — the server calls
SigNoz's Query Range API and attaches a bounded span summary (`GET /api/signoz/evidence`), with
a deep link to the full trace. Honest note: I also wired the SigNoz MCP server for coding-agent
handoffs, but stdio transport hung often enough that the product path prefers the HTTP API; MCP
is documented as PARTIAL.

## Griffin: covering the cold start

SigNoz's anomaly detection is seasonal; new agents have no season. Griffin is ArcNet's
per-metric statistical baseline — currently a **MAD z-score** judge (a TabFM forecasting path is
speced and stubbed behind a flag, but MAD is what runs, and the UI says so). It reads recent
history, flags outliers, and emits `arcnet.anomaly` back through the same signal path — so a
token-rate runaway gets caught by Griffin first, then confirmed by the SigNoz alert. Outlier →
report; normal → silence.

## The Time Machine: replay your own incidents

This is the piece I haven't seen elsewhere at the session level. Every session is recorded as a
replayable transcript (SQLite, not span attributes — traces truncate). The Time Machine replays
a recorded incident against a **different model or prompt**: same goal, same tool outputs
(mocked from the transcript), same guardrails — only the brain changes. Three runs at
temperature 0, majority verdict, honest `inconclusive` when runs disagree.

Two recorded heroes ship in the demo DB. The injection incident: baseline *attempted* the
injected exfiltration (the shield contained it) — the candidate never follows it at all. The
runaway loop: baseline got killed at 19 steps — the candidate stops itself at 5 and reports.
Both verdicts cite the numbers the runs actually produced. LangSmith and Braintrust replay a
call or a dataset row; this replays the whole recorded agent session, and that difference is
exactly what turns your trace history into a behavioral regression suite.

## Built for the agents that fix agents

Every HQ view has a machine-readable twin at `GET /api/agent-view/{view}/{id}` — same data,
cross-linked (`session → case_file → threats → models`) so a coding agent walks the incident
graph without guessing URLs. Errors return `{detail, hint}` with the next call to make. And
when it's time to improve an observed agent, `GET /api/agents/{id}/model-intel` returns
candidates from a dated model catalog with cost projections computed **only** from that agent's
recorded token totals, and a reasoning-tier recommendation that cites its recorded threat rate
and replay verdicts. Every number is either a labeled list-price estimate or derived from rows
in the database — the response carries its own honesty string saying so.

## What I'd tell you before you build this

1. **Verify the semconv before writing dashboards.** OpenInference ≠ `gen_ai.*`; one evening of
   span-spelunking saved every panel after it.
2. **SQLite-primary for anything you'll replay.** Span attributes truncate; transcripts are data.
3. **The inline fast-path matters.** Alert pipelines are seconds-to-minutes; a guard block
   should steer the agent in milliseconds, with the alert as the record.
4. **ClickHouse SQL panels are the escape hatch** when the query builder runs out.
5. **Measure honestly.** The repo carries a measured readiness doc (~64%, hard-capped at 65
   until the remaining exits pass) instead of a feature list that implies 95%. Judges and users
   can both read `docs/20-honest-progress.md`.

## Run it

```bash
git clone https://github.com/chiruu12/arcnet && cd arcnet
uv sync && ./scripts/run-demo.sh        # HQ on :5173, server :8000, AgentOS :7777
cd deploy && foundryctl cast -f casting.yaml   # optional: self-hosted SigNoz on :8080
```

The repo is MIT, the demo DB ships with both recorded heroes, and
`scripts/e2e_product_coherence.py` is the offline self-check that proves the loop end to end.

*Built solo for the Agents of SigNoz hackathon (Track 1: AI & Agent Observability).*
