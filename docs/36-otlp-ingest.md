# 36 — OTLP ingest: watch any framework's agents

ArcNet's server speaks standard OTLP/HTTP on `POST /v1/traces`. Any framework with an
[OpenInference](https://github.com/Arize-ai/openinference) instrumentor — LangChain, LlamaIndex,
CrewAI, the OpenAI Agents SDK, DSPy, LiteLLM, Agno — can feed the fleet with one pip install and
one exporter pointed at ArcNet. No ArcNet SDK required.

## What you get (and don't)

Ingested sessions are **observe-only**: they appear in `fleet_health` and the session lists with
tokens, tool calls/errors, model, cost estimates, goal excerpt, and timestamps, and Griffin picks
up their token series. What OTLP spans do **not** carry is a replayable transcript or guard
verdicts — the Time Machine and the Unplug shield need the SDK integration (docs/02). The API is
additive (docs/12).

## Quickstart (any framework, ~5 minutes)

```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http \
            openinference-instrumentation-langchain   # or -crewai, -llama-index, -openai, -agno…
```

```python
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider(resource=Resource.create({"service.name": "my-agent"}))
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://127.0.0.1:8000/v1/traces"))
)
trace.set_tracer_provider(provider)

from openinference.instrumentation.langchain import LangChainInstrumentor
LangChainInstrumentor().instrument()
# run your agent as usual — it now shows up in ArcNet's fleet
```

Or configure by environment instead of code:

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:8000/v1/traces
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf   # http/json also accepted
export OTEL_SERVICE_NAME=my-agent
```

## Identity and grouping

| Concept | Attribute | Fallback |
|---|---|---|
| Agent | resource attr `arcnet.agent_id` | resource attr `service.name`, else `otlp-agent` |
| Session | span attr `session.id` (OpenInference `using_session`) | one session per trace id (`s_otlp_<trace12>`) |
| Model | `llm.model_name` on LLM spans | none |
| Tokens | `llm.token_count.prompt` / `.completion` / `.total` | summed per session across batches |
| Goal | `input.value` on the root AGENT/CHAIN span | none (excerpted to 2,000 chars) |
| Status | any span status ERROR → `error` | `completed` |

Batches merge incrementally: a long-running session exported over many batches accumulates tokens
and extends `ended_at` instead of clobbering earlier rows.

## Auth

Writes are open on localhost by default. If `ARCNET_WRITE_SECRET` is set, send it from the
exporter:

```bash
export OTEL_EXPORTER_OTLP_HEADERS="X-Arcnet-Write-Secret=<secret>"
```

## Limits

- Body cap 4 MiB per export request (`422` beyond it — lower your batch size).
- Malformed payloads return `400` with `{detail, hint}`.
- Spans without OpenInference attributes still count toward session timestamps/status, but carry
  no tokens or tool stats.

## Verified

`server/tests/test_otlp_ingest.py` (10 offline tests: JSON + protobuf encodings, incremental
merge, trace-fallback grouping, error status, identity override, auth, bounds) plus a live proof:
a real `opentelemetry-sdk` + `OTLPSpanExporter(http/protobuf)` emitter landed an AGENT/LLM/TOOL
trace in `fleet_health` with exact token counts and an `error` status from a failing tool span.
