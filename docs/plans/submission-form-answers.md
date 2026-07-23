# Submission form — ready-to-paste answers

Form: https://forms.gle/xv1TXSiC54MEWujRA ("Agents of SigNoz Submissions").
Fill personal fields yourself; paste/edit the paragraphs below. Submit **Sunday morning** — the
form shows no cutoff time, so don't ride the deadline.

| Field | Value |
|---|---|
| Email | (yours) |
| Team name | (yours — solo) |
| Submitter | (your name) |
| Track | **Track 1: AI & Agent Observability** |
| GitHub link | https://github.com/chiruu12/arcnet |
| Deployed link (optional) | leave blank (local-first: `./scripts/run-demo.sh`) |
| YouTube video | (unlisted link — record per `video-script.md`) |
| Blog link | (publish `blog-draft.md` first) |

## Project description (paste + edit)

ArcNet is observability and active defense for AI agent fleets — agents that watch themselves
and get better. Every agent is traced end-to-end into self-hosted SigNoz (OpenTelemetry /
OpenInference), and every source it ingests carries a trust level via unplug-ai guardrails at
four checkpoints, so prompt injection through scraped content is caught at the boundary, with
the guard verdict (rule, pattern class, risk score) recorded as structured data. SigNoz alerts
loop back through a webhook into steer/kill signals the running agent obeys in seconds. Griffin,
a per-metric MAD statistical baseline, flags runaway agents from minute one — before seasonal
anomaly rules have history. The headline is the Time Machine: every session is recorded as a
replayable transcript, and ArcNet replays a real incident against a different model — same
goal, same tool outputs, same guardrails — producing an honest three-run verdict, which turns
your trace history into a behavioral regression suite. Every view has a machine-readable
agent-view twin with cross-links, and a model-intelligence endpoint recommends upgrades with
cost projections computed only from the agent's own recorded tokens. The repo ships a measured
honesty doc (~64% readiness, hard-capped) instead of feature theater.

## How we used SigNoz (paste + edit)

Self-hosted SigNoz is the observability backbone. Agno agents are instrumented with
openinference-instrumentation-agno, so traces land in SigNoz as {agent}.run → {model}.invoke →
{tool} waterfalls with token and cost attributes, plus custom arcnet.* span attributes for
guard telemetry (checkpoint, action, risk score, rule, pattern class). We built four
dashboards — Fleet Ops, Threats & Trust (including a ClickHouse SQL panel for a join the query
builder can't express), Cost & Tokens, and the Agno template — and six alert rules on the v5
queries payload, paired with SigNoz's native seasonal anomaly rule. Alerts POST to our webhook
and become steer/kill signals delivered to the running agent, closing an
observe→detect→self-correct loop. Case-file exports attach bounded span evidence fetched
through the SigNoz Query Range API with deep links back to the trace, and we wired the SigNoz
MCP server for coding-agent handoffs (documented honestly as PARTIAL — the HTTP API is the
reliable path). Setup, span-name verification notes, and provisioning scripts are in the repo
(`docs/04`, `deploy/`).

## Hackathon experience (paste + edit — personal voice)

Genuinely fun and genuinely hard in the right places. The best moment was watching the first
live replay verdict come back honest — `mixed`, not the flattering answer — and deciding to
keep it that way; the honesty regime (measured ~64% readiness with a hard cap, limitations at
the top of the README) ended up shaping the product more than any feature. Verifying what the
OpenInference instrumentor actually emits before writing dashboards saved days, and SigNoz's
ClickHouse SQL panels were the escape hatch I didn't know I needed. I'm keeping ArcNet alive
after the event — my own agents run under it now.

## Pre-submit checklist

- [ ] Blog published, URL works logged-out
- [ ] Video uploaded (unlisted), plays logged-out, < 3 min
- [ ] README screenshots in place (5 slots incl. model-intel)
- [ ] `git log -1` on GitHub matches local main; repo public
- [ ] Form submitted; screenshot the confirmation page
