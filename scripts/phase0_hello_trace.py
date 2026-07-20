#!/usr/bin/env python3
"""Phase 0 B5/B6: Hello Agno → SigNoz via openinference; dump real span/attr names."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

OTLP = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
MODEL = os.getenv("ARCNET_MODEL", "gpt-4o-mini")


def setup_otel(service_name: str = "arcnet-hello") -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, ConsoleSpanExporter

    resource = Resource.create(
        {
            "service.name": service_name,
            "arcnet.session_id": "phase0_hello",
            "arcnet.agent_id": "hello",
        }
    )
    provider = TracerProvider(resource=resource)
    endpoint = OTLP.rstrip("/") + "/v1/traces"
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    # Also capture locally so we can record attrs even if Query Range isn't ready yet
    dump_path = ROOT / "docs" / "_phase0_spans.jsonl"
    dump_path.write_text("")

    class JsonlExporter(ConsoleSpanExporter):
        def export(self, spans):  # type: ignore[override]
            with dump_path.open("a") as f:
                for span in spans:
                    attrs = dict(span.attributes or {})
                    f.write(
                        json.dumps(
                            {
                                "name": span.name,
                                "kind": str(span.kind),
                                "attrs": {k: str(v)[:500] for k, v in attrs.items()},
                                "events": [
                                    {
                                        "name": e.name,
                                        "attrs": {k: str(v)[:200] for k, v in (e.attributes or {}).items()},
                                    }
                                    for e in span.events
                                ],
                            }
                        )
                        + "\n"
                    )
            return super().export(spans)

    # Quiet console — write jsonl only
    from opentelemetry.sdk.trace.export import SpanExportResult

    class FileOnlyExporter:
        def export(self, spans):
            with dump_path.open("a") as f:
                for span in spans:
                    attrs = dict(span.attributes or {})
                    f.write(
                        json.dumps(
                            {
                                "name": span.name,
                                "attrs": {k: str(v)[:500] for k, v in attrs.items()},
                            }
                        )
                        + "\n"
                    )
            return SpanExportResult.SUCCESS

        def shutdown(self):
            return None

    provider.add_span_processor(SimpleSpanProcessor(FileOnlyExporter()))
    trace.set_tracer_provider(provider)

    from openinference.instrumentation.agno import AgnoInstrumentor

    AgnoInstrumentor().instrument()
    print(f"OTLP → {endpoint}")


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("NO_OPENAI_KEY — skip live LLM hello trace", file=sys.stderr)
        return 2

    setup_otel()

    from agno.agent import Agent
    from agno.models.openai import OpenAIChat
    from agno.tools.decorator import tool

    @tool
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    agent = Agent(
        name="hello_arcnet",
        model=OpenAIChat(id=MODEL),
        tools=[add],
        instructions="You are a tiny math helper. Use the add tool.",
        markdown=False,
    )
    print(f"Running hello agent with model={MODEL}…")
    result = agent.run("What is 21 + 21? Use the add tool.")
    print("content:", getattr(result, "content", result))
    # Force flush
    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush(timeout_millis=10000)
    time.sleep(2)

    dump = ROOT / "docs" / "_phase0_spans.jsonl"
    print(f"\n=== Local span dump ({dump}) ===")
    if dump.exists():
        for line in dump.read_text().splitlines():
            obj = json.loads(line)
            print(f"- {obj['name']}")
            for k in sorted(obj["attrs"]):
                if any(
                    p in k
                    for p in (
                        "llm.",
                        "openinference",
                        "tool",
                        "input",
                        "output",
                        "gen_ai",
                        "arcnet",
                    )
                ):
                    print(f"    {k}={obj['attrs'][k][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
