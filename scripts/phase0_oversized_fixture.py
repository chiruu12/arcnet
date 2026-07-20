#!/usr/bin/env python3
"""Phase 0 B10: Find span-attribute truncation point with an oversized fixture."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

OTLP = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")


def main() -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExportResult

    sizes = [1_000, 4_000, 8_000, 16_000, 32_000, 64_000, 128_000, 256_000]
    results = []
    dump = ROOT / "docs" / "_phase0_truncation.jsonl"
    dump.write_text("")

    class Capture:
        def export(self, spans):
            with dump.open("a") as f:
                for span in spans:
                    attrs = dict(span.attributes or {})
                    payload = attrs.get("arcnet.fixture", "")
                    f.write(
                        json.dumps(
                            {
                                "name": span.name,
                                "attr_len": len(str(payload)),
                                "keys": list(attrs.keys()),
                            }
                        )
                        + "\n"
                    )
            return SpanExportResult.SUCCESS

        def shutdown(self):
            return None

    resource = Resource.create({"service.name": "arcnet-truncation"})
    provider = TracerProvider(resource=resource)
    endpoint = OTLP.rstrip("/") + "/v1/traces"
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    provider.add_span_processor(SimpleSpanProcessor(Capture()))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("arcnet.phase0")

    for n in sizes:
        payload = ("X" * n) + f"|MARK|{n}|"
        with tracer.start_as_current_span("oversized_fixture") as span:
            span.set_attribute("arcnet.fixture", payload)
            span.set_attribute("arcnet.fixture_len", n)
        results.append({"requested": n})
        print(f"emitted fixture size={n}")

    if hasattr(provider, "force_flush"):
        provider.force_flush(timeout_millis=15000)
    time.sleep(2)

    captured = [json.loads(l) for l in dump.read_text().splitlines() if l.strip()]
    print("\nLocal processor saw attr lengths:")
    for c in captured:
        print(f"  {c['attr_len']}")

    # Note: local SimpleSpanProcessor sees pre-export values; collector may truncate.
    # Record both: SDK accepts all sizes locally; collector/backend ceiling needs Query Range round-trip.
    summary = {
        "sdk_local_max_accepted": max((c["attr_len"] for c in captured), default=0),
        "sizes_tested": sizes,
        "note": (
            "SDK set_attribute accepted all tested sizes locally. "
            "Backend truncation must be confirmed by querying the span back from SigNoz "
            "(Query Range / trace detail). Transcripts remain SQLite-primary regardless."
        ),
    }
    out = ROOT / "docs" / "_phase0_truncation_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
