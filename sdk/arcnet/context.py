"""In-process ArcNet runtime handle (set by arcnet.init)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Tracer
    from unplug import Guard, TaintedText

    from arcnet.signals import SignalClient
    from arcnet.transcript import TranscriptRecorder


@dataclass
class ArcnetRuntime:
    service_name: str
    session_id: str
    agent_id: str
    exposure: str  # forward_facing | internal
    otlp_endpoint: str
    server_url: str
    guard: Guard
    signals: SignalClient
    tracer: Tracer
    meter: Meter
    threats_detected: Counter
    guard_latency: Histogram
    tokens_total: Counter
    cost_usd: Counter
    tool_calls: Counter
    signals_emitted: Counter
    taint_sources: list[TaintedText] = field(default_factory=list)
    transcript: TranscriptRecorder | None = None
    model: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


_runtime: ContextVar[ArcnetRuntime | None] = ContextVar("arcnet_runtime", default=None)


def get_runtime() -> ArcnetRuntime:
    rt = _runtime.get()
    if rt is None:
        raise RuntimeError("arcnet.init() has not been called in this context")
    return rt


def set_runtime(rt: ArcnetRuntime | None) -> None:
    _runtime.set(rt)


def try_get_runtime() -> ArcnetRuntime | None:
    return _runtime.get()
