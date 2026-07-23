"""arcnet.init() — OTel providers + AgnoInstrumentor + Guard + signal client."""

from __future__ import annotations

import logging
import os

from openinference.instrumentation.agno import AgnoInstrumentor
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from unplug import GuardConfig

from arcnet.context import ArcnetRuntime, set_runtime
from arcnet.guard_factory import build_guard
from arcnet.ids import new_id
from arcnet.signals import SignalClient

logger = logging.getLogger("arcnet")

_INSTRUMENTED = False


def init(
    service_name: str = "arcnet",
    *,
    session_id: str | None = None,
    agent_id: str = "agent_j",
    otlp_endpoint: str | None = None,
    server_url: str | None = None,
    guard_config: GuardConfig | None = None,
    exposure: str = "internal",
    model: str | None = None,
) -> ArcnetRuntime:
    """Wire OTel (traces+metrics), AgnoInstrumentor, Guard, stub signal client.

    Logs correlation lands in Phase 2 (OTLP logs exporter optional here).
    """
    global _INSTRUMENTED

    otlp = (otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")).rstrip(
        "/"
    )
    server = (server_url or os.getenv("ARCNET_SERVER_URL", "http://localhost:8000")).rstrip("/")
    sid = session_id or new_id("s_")

    resource = Resource.create(
        {
            "service.name": service_name,
            "arcnet.session_id": sid,
            "arcnet.agent_id": agent_id,
            "arcnet.exposure": exposure,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp}/v1/traces"))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{otlp}/v1/metrics"),
        export_interval_millis=5000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Structured stdlib logs → OTLP with trace_id/span_id correlation (Phase 2).
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{otlp}/v1/logs"))
        )
        set_logger_provider(logger_provider)
        # Attach once so arcnet.* loggers (and root) carry trace context into SigNoz.
        root = logging.getLogger()
        if not any(isinstance(h, LoggingHandler) for h in root.handlers):
            root.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    except Exception:  # noqa: BLE001
        logger.debug("OTLP log exporter unavailable; continuing with traces+metrics", exc_info=True)

    if not _INSTRUMENTED:
        AgnoInstrumentor().instrument()
        _INSTRUMENTED = True

    guard = build_guard(guard_config)
    signals = SignalClient(server_url=server, session_id=sid, agent_id=agent_id)
    signals.start()
    tracer = trace.get_tracer("arcnet")
    meter = metrics.get_meter("arcnet")
    anomaly = meter.create_counter(
        "arcnet.anomaly",
        description="Griffin anomaly detections (1 per outlier)",
    )

    rt = ArcnetRuntime(
        service_name=service_name,
        session_id=sid,
        agent_id=agent_id,
        exposure=exposure,
        otlp_endpoint=otlp,
        server_url=server,
        guard=guard,
        signals=signals,
        tracer=tracer,
        meter=meter,
        threats_detected=meter.create_counter(
            "arcnet.threats.detected",
            description="Threat findings from Unplug checkpoints",
        ),
        guard_latency=meter.create_histogram(
            "arcnet.guard.latency",
            unit="ms",
            description="Guard checkpoint latency",
        ),
        tokens_total=meter.create_counter(
            "arcnet.tokens.total",
            description="Total LLM tokens",
        ),
        cost_usd=meter.create_counter(
            "arcnet.cost.usd",
            unit="USD",
            description="Estimated LLM cost",
        ),
        tool_calls=meter.create_counter(
            "arcnet.tool.calls",
            description="Tool invocations",
        ),
        signals_emitted=meter.create_counter(
            "arcnet.signals.emitted",
            description="Signals emitted",
        ),
        anomaly=anomaly,
        model=model or os.getenv("ARCNET_MODEL"),
    )
    set_runtime(rt)
    logger.info(
        "arcnet.init service=%s session=%s agent=%s otlp=%s",
        service_name,
        sid,
        agent_id,
        otlp,
    )
    return rt


def shutdown() -> None:
    from arcnet.context import try_get_runtime

    rt = try_get_runtime()
    if rt is not None:
        rt.signals.stop()
    set_runtime(None)
    tp = trace.get_tracer_provider()
    if hasattr(tp, "force_flush"):
        tp.force_flush()  # type: ignore[call-arg]
    mp = metrics.get_meter_provider()
    if hasattr(mp, "force_flush"):
        mp.force_flush()  # type: ignore[call-arg]


def bind_session(session_id: str) -> None:
    from arcnet.context import get_runtime

    rt = get_runtime()
    rt.session_id = session_id
    rt.signals.session_id = session_id
    rt.taint_sources.clear()
