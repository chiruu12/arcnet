# The maintenance loop your agent fleet is missing

> FINAL copy for the Agents of SigNoz submission blog. Paste to dev.to / Hashnode / personal site,
> then put the URL in the form. Passes the fact checklist in [`../35-blog-script.md`](../35-blog-script.md);
> if you edit, keep the numbers and caveats as they are — they match the shipped build.

We have gotten very good at building agents, and we are still terrible at maintaining them.

Normal software has a whole maintenance discipline: monitoring, incident response, regression
suites, staged rollouts. An agent is a model wrapped in a harness — prompts, tools, guardrails,
routing — and that harness rots like any other software. Tools change. Prompts drift. A model
swap that looks great on a benchmark quietly reintroduces the exact failure you fixed last month.
When something goes wrong in production, what you usually have is a trace viewer and a shrug.

ArcNet is my attempt at the missing discipline, built on [SigNoz](https://signoz.io) for the
Agents of SigNoz hackathon. It treats an agent fleet the way an SRE treats a service: watch it,
defend it, file real incidents, and prove a fix before you ship it. Concretely it runs three
loops around your fleet, at three speeds.

## Three loops, one system

```
Agno agents (+ Unplug guardrails)          React HQ (mission control)
        │  OpenTelemetry (OpenInference)          │
        ▼                                         ▼
   SigNoz (self-hosted) ◄──── webhooks ────► ArcNet server (FastAPI + SQLite)
        │   dashboards · alerts · traces          │  signals · threats · replays · case files
        └────────── Query Range API ──────────────┘
```

**The runtime loop (seconds).** Observe everything, block what crosses the trust boundary, steer
the agent back on course while it is still running.

**The incident loop (minutes).** Turn a blocked attack or a runaway session into a case file a
coding agent can actually consume, and hand it off to fix the harness at the source.

**The upgrade loop (days).** When it is time to develop the agent — new model, new prompt —
replay the incidents your fleet already recorded against the candidate and read the verdict
before you change routing.

Most observability products stop after the first half of loop one. The rest of this post walks
through how each loop is wired, including the SigNoz details that cost me real time.

## Loop 1: observe and defend

Demo agents run on Agno's AgentOS. Every agent is wrapped by
[unplug-ai](https://pypi.org/project/unplug-ai/) guardrails at four checkpoints: input,
retrieved content, tool call, output. Every ingested source gets a trust level, and every guard
verdict (rule, pattern class, risk score) becomes structured telemetry instead of a boolean.

The canonical incident: a forward-facing agent scrapes a page with a hidden instruction. The
page itself scans clean, so ArcNet lets the agent read it. What it will not let through is the
consequence — the moment that tainted content tries to become a `send_email` call, the tool call
is blocked at the trust boundary and a `steer` signal reaches the running agent on an inline
fast-path in milliseconds. Guard blocks should not wait for an alert pipeline; the SigNoz alert
lands right behind as the system of record.

The SigNoz wiring, since that is the part you came for:

- **OpenInference semconv, not `gen_ai.*`.** I instrumented Agno with
  `openinference-instrumentation-agno`. The spans you actually get are
  `{agent}.run → {model}.invoke → {tool}` with OpenInference attributes. Every dashboard query
  and alert below is written against what the instrumentor really emits, verified span by span
  before writing a single panel.
- **Custom `arcnet.guard.*` attributes** carry checkpoint, action, risk score, rule, and pattern
  class, so a blocked exfiltration is a span you can aggregate and alert on, joined back to the
  session.
- **Four dashboards** — Fleet Ops, Threats & Trust, Cost & Tokens, and the prebuilt Agno
  template. When SigNoz's query builder ran out of expressiveness, a raw ClickHouse SQL panel
  over the traces table kept going. That escape hatch is underrated.
- **Alerts want the v5 `queries` payload.** Legacy alert payloads are rejected; this cost me an
  evening. Alerts POST to `/webhooks/signoz` on the ArcNet server and become signals (steer,
  pause, kill) delivered through Agno's hooks and run cancellation.
- **Query Range API for evidence.** Case files don't screenshot dashboards; the server pulls a
  bounded span summary over HTTP with a deep link to the full trace. I also wired the SigNoz MCP
  server, but stdio transport hung often enough that the product path prefers HTTP. MCP is
  documented as PARTIAL, and I would make the same call again.

One more piece: SigNoz's seasonal anomaly rule needs days of history and five-minute windows. A
brand-new agent has no season. Griffin is ArcNet's per-metric statistical baseline — a MAD
z-score judge, and the UI says exactly that — which flags a token-rate runaway from minute one.
Outlier, report; normal, silence. The SigNoz rule confirms it once there is history to confirm
with.

## Loop 2: hand the incident to the agent that fixes agents

Watching a human read a dashboard and then paste fragments into a coding assistant is what
convinced me this loop needed to be first-class. So every HQ view has a machine-readable twin at
`GET /api/agent-view/{view}/{id}` — same records, bounded, cross-linked
(`session → case_file → threats → models`) so a coding agent walks the incident graph without
guessing URLs. Errors return `{detail, hint}` with the next call to make. Agent-oriented GETs
also accept `?format=toon` ([TOON](https://toonformat.dev) — tabular and token-efficient), and
the HQ UI can flip any view to its agent twin so you can see what the machine sees.

A case file exports as a zip: `case-file.md` with a fix-prompt preamble, plus `case-file.json`.
Root cause, trust provenance, guard verdicts, a SigNoz trace pointer. You hand that to whatever
coding agent maintains your harness, and it starts from evidence instead of a screenshot.

## Loop 3: prove the upgrade on your own history

This is the piece I have not seen elsewhere at the session level. Every session is recorded as a
replayable transcript in SQLite — transcripts are data, and span attributes truncate. The Time
Machine replays a recorded incident against a different model or prompt: same goal, same tool
outputs mocked from the transcript, same guardrails. Only the brain changes. Three runs at
temperature 0, majority verdict, and an honest `inconclusive` when the runs disagree.
Temperature 0 is variance reduction, not determinism.

Two recorded incidents ship in the demo DB. On the injection incident, the recorded baseline
followed the poisoned page's social engineering and attempted the exfiltration (the taint guard
contained it); the candidate resisted it in all three replays, at several times the baseline's
cost. On the runaway-loop incident, the baseline paginated until ArcNet killed it; the candidate
breaks the loop on its own. Verdicts come back `mixed` more often than green: security or
reliability improves and cost rises, and you get to see that tradeoff before you change routing,
not after. LangSmith and Braintrust replay a call or a dataset row. ArcNet replays the whole
recorded agent session, and that difference is what turns your trace history into a behavioral
regression suite for the harness.

The develop half of the loop is model intelligence. `GET /api/agents/{id}/model-intel` projects
candidates from a dated static catalog (currently `2026-07e` — the highlights include Kimi, Qwen,
and DeepSeek ids). Every dollar figure is a labeled list-price estimate computed from that
agent's own recorded token totals, never an invoice. Recommendations are bucketed
(`recommended_upgrade`, `cost_saver`, `peer`, `not_advised`) with fit reasons and blockers cited
from recorded evidence, and a reasoning-tier suggestion appears only when the agent's recorded
threat rate or contested replay verdicts justify it.

Apply is human-gated on purpose. The HQ Agent proposes; a human confirms; SQLite updates; and
the UI says out loud when an AgentOS reload is still manual. Nothing hot-swaps a production
model silently.

## What I'd tell you before you build this

1. **Verify the semconv before writing dashboards.** OpenInference is not `gen_ai.*`. One
   evening of span-spelunking saved every panel after it.
2. **SQLite-primary for anything you'll replay.** Traces age out and attributes truncate;
   transcripts are the product data.
3. **The inline fast-path matters.** Alert pipelines are seconds to minutes. A guard block
   should steer the agent in milliseconds, with the alert as the record.
4. **Label your price math.** List price times recorded tokens is genuinely useful. Pretending
   it is the invoice is not.
5. **Measure honestly.** The repo carries a measured readiness doc with a hard cap
   (`docs/20-honest-progress.md`) instead of a feature list that implies done. Judges and users
   can both read it.

## Run it

```bash
git clone https://github.com/chiruu12/arcnet && cd arcnet
cp .env.example .env                       # OPENAI_API_KEY only needed for live replay
uv sync --all-packages && cd hq && pnpm install && cd ..
./scripts/run-demo.sh                      # HQ http://localhost:5173 · API :8000 · AgentOS :7777
```

A cold clone renders both recorded incidents, the Time Machine verdicts, and the case files with
no API key. SigNoz on `:8080` is the optional depth layer:
`cd deploy && foundryctl cast -f casting.yaml`, then provision the service-account key.

Honest limitations, so you don't have to find them yourself: Griffin is MAD today (a TabFM path
is stubbed, not live). SigNoz MCP stdio is PARTIAL; the HTTP handoff is the product path. HITL
approve/reject is SQLite bookkeeping with a best-effort relay, not a full pause/resume. Replay
verdicts are allowed to be `mixed` or `inconclusive`, because that is what real replays return.

If you run agents in production, or you are about to change the model behind one: clone it, open
the Time Machine on the runaway-loop session, and read the verdict it actually prints. Then ask
yourself how you did your last model swap.

*Built solo for the Agents of SigNoz hackathon (Track 1: AI & Agent Observability). MIT.*
