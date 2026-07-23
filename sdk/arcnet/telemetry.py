"""OTel helpers for arcnet.* spans, metrics, and logs."""

from __future__ import annotations

import logging
import time
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from arcnet.context import ArcnetRuntime, try_get_runtime
from arcnet.guard_factory import serialize_findings, top_finding

logger = logging.getLogger("arcnet.guard")


def _common_attrs(rt: ArcnetRuntime) -> dict[str, str]:
    return {
        "arcnet.session_id": rt.session_id,
        "arcnet.agent_id": rt.agent_id,
        "arcnet.exposure": rt.exposure,
    }


def emit_guard_telemetry(
    *,
    checkpoint: str,
    action: str,
    risk_score: float,
    findings: list[Any],
    latency_ms: float,
    trust_level: str | None = None,
    guard_verdict: dict[str, Any] | None = None,
) -> None:
    """Emit arcnet.guard span + metrics + structured log for one checkpoint result."""
    rt = try_get_runtime()
    if rt is None:
        return

    top = top_finding(findings)
    top_category = getattr(top, "category", "") or "" if top else ""
    rule = getattr(top, "subcategory", "") or "" if top else ""
    pattern_class = getattr(top, "stage", "") or "" if top else ""

    attrs = {
        **_common_attrs(rt),
        "arcnet.guard.checkpoint": checkpoint,
        "arcnet.guard.action": action,
        "arcnet.guard.risk_score": float(risk_score),
        "arcnet.guard.findings_count": len(findings),
        "arcnet.guard.top_category": top_category,
    }
    if rule:
        attrs["arcnet.guard.rule"] = rule
    if pattern_class:
        attrs["arcnet.guard.pattern_class"] = pattern_class
    if trust_level:
        attrs["arcnet.guard.trust_level"] = trust_level

    with rt.tracer.start_as_current_span("arcnet.guard") as span:
        for k, v in attrs.items():
            span.set_attribute(k, v)
        for f in findings:
            span.add_event(
                "arcnet.finding",
                attributes={
                    "category": getattr(f, "category", "") or "",
                    "subcategory": getattr(f, "subcategory", "") or "",
                    "stage": getattr(f, "stage", "") or "",
                    "score": float(getattr(f, "score", 0.0) or 0.0),
                    "evidence": str(getattr(f, "evidence", "") or "")[:200],
                },
            )
        if action == "block":
            span.set_status(Status(StatusCode.ERROR, "guard block"))
        else:
            span.set_status(Status(StatusCode.OK))

    rt.guard_latency.record(
        latency_ms,
        {"checkpoint": checkpoint, "agent_id": rt.agent_id},
    )
    if action != "allow":
        rt.threats_detected.add(
            1,
            {
                "category": top_category or "unknown",
                "action": action,
                "agent_id": rt.agent_id,
            },
        )
        _post_threat(
            rt,
            checkpoint,
            action,
            top_category,
            risk_score,
            findings,
            trust_level,
            guard_verdict=guard_verdict,
        )

    logger.info(
        "guard checkpoint=%s action=%s risk=%.2f findings=%d rule=%s",
        checkpoint,
        action,
        risk_score,
        len(findings),
        rule or "-",
        extra={"trace_id": format(trace.get_current_span().get_span_context().trace_id, "032x")},
    )


def _post_threat(
    rt: ArcnetRuntime,
    checkpoint: str,
    action: str,
    category: str,
    risk_score: float,
    findings: list[Any],
    trust_level: str | None,
    *,
    guard_verdict: dict[str, Any] | None = None,
) -> None:
    import httpx

    from arcnet.ids import new_id

    evidence = ""
    subcategory = ""
    pattern_class = ""
    if findings:
        top = top_finding(findings)
        if top is not None:
            evidence = str(getattr(top, "evidence", "") or "")[:200]
            subcategory = getattr(top, "subcategory", "") or ""
            pattern_class = getattr(top, "stage", "") or ""

    span = trace.get_current_span()
    ctx = span.get_span_context()
    payload: dict[str, Any] = {
        "threat_id": new_id("thr_"),
        "session_id": rt.session_id,
        "agent_id": rt.agent_id,
        "checkpoint": checkpoint,
        "action": action,
        "category": category or None,
        "subcategory": subcategory or None,
        "risk_score": risk_score,
        "trust_level": trust_level,
        "evidence": evidence,
        "trace_id": format(ctx.trace_id, "032x") if ctx.is_valid else None,
        "span_id": format(ctx.span_id, "016x") if ctx.is_valid else None,
        "findings_detail": serialize_findings(findings),
    }
    if pattern_class:
        payload["pattern_class"] = pattern_class
    if guard_verdict:
        payload["guard_verdict"] = guard_verdict
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{rt.server_url}/api/threats", json=payload).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("threat post failed: %s", exc)


def post_source(
    *,
    origin: str,
    trust_level: str,
    scan_action: str,
    findings: list[Any] | int | None = None,
    guard_verdict: dict[str, Any] | None = None,
) -> None:
    import httpx

    from arcnet.ids import new_id

    rt = try_get_runtime()
    if rt is None:
        return
    if isinstance(findings, int):
        findings_list: list[Any] = []
        findings_count = findings
    else:
        findings_list = list(findings or [])
        findings_count = len(findings_list)
    payload: dict[str, Any] = {
        "source_id": new_id("src_"),
        "session_id": rt.session_id,
        "agent_id": rt.agent_id,
        "origin": origin,
        "trust_level": trust_level,
        "scan_action": scan_action,
        "findings": findings_count,
        "findings_detail": serialize_findings(findings_list) if findings_list else None,
    }
    if guard_verdict:
        payload["guard_verdict"] = guard_verdict
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{rt.server_url}/api/sources", json=payload).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("source post failed: %s", exc)


def emit_run_usage(*, model: str, input_tokens: int, output_tokens: int, latency_ms: float) -> None:
    from arcnet.pricing import cost_usd

    rt = try_get_runtime()
    if rt is None:
        return
    cost = cost_usd(model, input_tokens, output_tokens)
    attrs = {"agent_id": rt.agent_id, "model": model}
    rt.tokens_total.add(input_tokens + output_tokens, attrs)
    rt.cost_usd.add(cost, attrs)
    if latency_ms > 0:
        # reuse guard histogram? no — duration is on spans; cost/tokens are the Phase 1 metrics
        pass


class LatencyTimer:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0
