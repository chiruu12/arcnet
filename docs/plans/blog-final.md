# What I learned wiring an AI agent fleet into self-hosted SigNoz

*Paste-ready for Dev.to. ~1,380 words. No em dashes. Screenshot slots marked [SCREENSHOT N].*

---

I spent a week trying to answer one question about my own AI agents: when one of them does something stupid in production, how do I prove the fix worked?

For normal software the answer is boring. You have monitoring, an incident, a regression test, a staged rollout. For an agent you usually have a trace viewer and a shrug. So I built ArcNet on self-hosted SigNoz for the Agents of SigNoz hackathon, and most of what I learned was about SigNoz internals I could not have guessed from the docs.

Here are the parts that cost me real time.

## The setup

The stack is small. Agents run on Agno. An in-process SDK wraps them and does two jobs: OpenTelemetry instrumentation, and guardrails from `unplug-ai` at four checkpoints (input, retrieved content, tool call, output). Traces go to self-hosted SigNoz over OTLP. A FastAPI server reads back out of SigNoz, and a React UI sits on top.

Installing SigNoz was the easiest part, which surprised me. Foundry takes one file:

```yaml
apiVersion: v1alpha1
kind: Installation
metadata:
  name: signoz
spec:
  deployment:
    flavor: compose
    mode: docker
  signoz:
    spec:
      image: signoz/signoz:v0.133.0
```

```bash
foundryctl cast -f casting.yaml
```

That brings up SigNoz and its MCP server together and writes a `casting.yaml.lock` with checksums. I committed the lock file, and re-running `foundryctl forge` against it later produced a byte-identical file. That is a genuinely nice property for a hackathon judge or a teammate.

[SCREENSHOT 1: terminal showing `foundryctl cast` finishing, plus SigNoz UI loading on :8080]

## Lesson 1: check what your instrumentor actually emits

This is the one I would tell everyone.

I assumed Agno instrumentation would produce OpenTelemetry's `gen_ai.*` semantic conventions, because that is what the GenAI spec describes. I started sketching dashboard queries against `gen_ai.usage.input_tokens` before anything was running.

Then I turned it on. `openinference-instrumentation-agno` emits **OpenInference** conventions, which are a different attribute set. The spans I actually got were shaped like this:

```
agent_j.run
  └── gpt-4o.invoke
        └── search_tickets
```

Every panel I had sketched was querying attributes that did not exist. Nothing errored. The charts were just empty, which is a much worse failure mode than a crash.

So I stopped and spent an evening doing nothing but reading raw spans in the SigNoz trace view, writing down the exact attribute keys. Every dashboard and alert after that was written against verified keys. Those two hours saved days.

If you take one thing from this post: send one real request, open the trace, and read the attribute names with your own eyes before you write a single query. This is true for any instrumentor, not just this one.

[SCREENSHOT 2: SigNoz trace waterfall for `agent_j.run` with the attributes panel open]

## Lesson 2: custom attributes turn a guardrail into telemetry

A guardrail that returns true or false is not observable. You cannot chart it and you cannot alert on it.

So every guard verdict writes structured span attributes:

```python
span.set_attribute("arcnet.guard.checkpoint", "tool_call")
span.set_attribute("arcnet.guard.action", "block")
span.set_attribute("arcnet.guard.rule", "retrieved_source_in_side_effect")
span.set_attribute("arcnet.guard.risk_score", 0.85)
```

Now a blocked exfiltration attempt is a row I can aggregate by rule, group by agent, and alert on. The concrete case: an agent scrapes a page with a hidden instruction in it. The page scans clean at ingest, so the agent is allowed to read it. What gets blocked is the consequence, when that tainted content tries to become a `send_email` call.

That distinction only became visible to me because the checkpoint was an attribute. I had assumed the block happened at ingest. The data said otherwise.

[SCREENSHOT 3: Threats and Trust dashboard, blocked calls grouped by rule]

## Lesson 3: alerts want the v5 queries payload

I lost an evening here.

I was creating alert rules through the API using a payload shape I found in an older example. SigNoz rejected them. The current alerts API expects the v5 `queries` structure, and once I matched it, all six rules went in without complaint.

Worth checking your SigNoz version against the API reference before you write the automation, rather than after.

My alerts POST to a webhook on the ArcNet server, which turns them into steer, pause, or kill signals delivered back into the running agent through Agno hooks.

One thing I got wrong on the first pass: I routed guard blocks through the alert pipeline too. Alerts take seconds to minutes, which is correct for humans and far too slow for stopping an agent mid-run. Guard blocks now take an inline fast path in the SDK, and the SigNoz alert lands behind it as the system of record. Use the alert pipeline for the record, not the reflex.

## Lesson 4: the ClickHouse SQL panel is the escape hatch

The SigNoz query builder covers most of what I wanted. For one panel it did not, because I needed a join the builder could not express.

SigNoz lets you drop to a raw ClickHouse SQL panel against the traces table. That unblocked me in about ten minutes. I would not build every panel this way, since the query builder survives schema changes better, but knowing the escape hatch exists changed how I approached the dashboards.

[SCREENSHOT 4: the ClickHouse SQL panel with its query visible]

## Lesson 5: traces are not your replay data

The feature I care most about replays a recorded agent session against a different model. Same goal, same tool outputs, same guardrails, only the model changes. It turns your incident history into a regression suite.

My first instinct was to rebuild sessions from spans. That does not work. Span attributes truncate, and traces age out of ClickHouse on a retention policy. Both are correct behavior for an observability backend and both are fatal if you need the exact transcript back in a month.

So sessions are recorded to SQLite as first class data, and SigNoz holds the telemetry. Traces are for observing. Transcripts are for replaying. When a case file needs evidence, the server pulls a bounded span summary through the Query Range API and attaches a deep link to the full trace, rather than trying to store the trace itself.

I also wired the SigNoz MCP server so a coding agent could pull trace details directly. The stdio transport hung often enough in my testing that the HTTP path became the product path. I have documented MCP as partial rather than claiming it works, because for my setup it did not work reliably.

## What actually changed my mind

The replay verdicts come back `mixed` more often than green. On my injection incident, the candidate model resisted the attack in all three replays and cost several times more than the baseline. That is not a clean win, and the tool says so.

I nearly built the verdict to round toward a recommendation. I am glad I did not. A tool that only ever says "upgrade" is a tool you stop believing after the second time.

## If you are starting this week

1. Send one request, open the trace, write down the real attribute names. Do this before any dashboard work.
2. Emit your domain decisions as span attributes. Booleans are invisible.
3. Check your SigNoz version against the alerts API reference before automating rule creation.
4. Keep your own copy of anything you need to replay later.
5. Let the tool return an unflattering answer.

Everything here ran on my machine with Docker, SigNoz v0.133.0, and Agno. Your span names will differ if you use a different instrumentor, which is exactly why lesson one is lesson one.

Code is at [github.com/chiruu12/arcnet](https://github.com/chiruu12/arcnet), Apache 2.0, including the `casting.yaml` and lock file if you want to bring up the same stack.

*Built solo for the Agents of SigNoz hackathon, Track 1. I used AI coding assistants throughout the build, and the numbers and behavior described here are from runs on my own machine.*
