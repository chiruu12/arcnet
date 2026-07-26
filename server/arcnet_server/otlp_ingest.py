"""OTLP/HTTP trace ingest — any OpenInference-instrumented framework feeds the fleet.

Accepts the standard OTLP/HTTP encodings on ``POST /v1/traces``:
``application/x-protobuf`` (SDK default) and ``application/json``. Spans are
grouped into sessions (``session.id`` attribute, else one session per trace)
under an agent identity (``arcnet.agent_id`` resource attribute, else
``service.name``), then merged incrementally into the existing ``agents`` /
``sessions`` rows so batches arriving over time accumulate instead of clobber.

Sessions ingested here are observe-only: fleet health, session lists, and
Griffin token series work; guard verdicts and replay need transcripts the OTLP
wire does not carry (docs/36).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

from arcnet_server import repository
from arcnet_server.db import now_ms
from arcnet_server.errors import api_error

MAX_BODY_BYTES = 4 * 1024 * 1024
GOAL_EXCERPT_CHARS = 2000
DEFAULT_AGENT_ID = "otlp-agent"

_OPENINFERENCE_KIND = "openinference.span.kind"
_SESSION_ID_ATTR = "session.id"
_AGENT_ID_RESOURCE_ATTR = "arcnet.agent_id"


# ---------------------------------------------------------------- attribute decoding


def _any_value_json(value: dict[str, Any]) -> Any:
    """Decode one OTLP-JSON AnyValue (protobuf JSON mapping encodes ints as strings)."""
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        try:
            return int(value["intValue"])
        except (TypeError, ValueError):
            return None
    if "doubleValue" in value:
        try:
            return float(value["doubleValue"])
        except (TypeError, ValueError):
            return None
    if "boolValue" in value:
        return bool(value["boolValue"])
    return None


def _attrs_json(raw: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(raw, list):
        return out
    for kv in raw:
        if isinstance(kv, dict) and isinstance(kv.get("key"), str) and isinstance(kv.get("value"), dict):
            out[kv["key"]] = _any_value_json(kv["value"])
    return out


def _any_value_pb(value: Any) -> Any:
    kind = value.WhichOneof("value")
    if kind == "string_value":
        return value.string_value
    if kind == "int_value":
        return int(value.int_value)
    if kind == "double_value":
        return float(value.double_value)
    if kind == "bool_value":
        return bool(value.bool_value)
    return None


def _attrs_pb(raw: Any) -> dict[str, Any]:
    return {kv.key: _any_value_pb(kv.value) for kv in raw}


# ---------------------------------------------------------------- wire → flat spans


def _flat_span(
    *,
    name: str,
    trace_id: str,
    parent_span_id: str,
    start_ns: int,
    end_ns: int,
    attrs: dict[str, Any],
    is_error: bool,
    resource: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "trace_id": trace_id,
        "parent_span_id": parent_span_id,
        "start_ns": start_ns,
        "end_ns": end_ns,
        "attrs": attrs,
        "is_error": is_error,
        "resource": resource,
    }


def _parse_json_body(body: bytes) -> list[dict[str, Any]]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise api_error(400, "malformed OTLP/JSON body", hint="send an ExportTraceServiceRequest")
    if not isinstance(payload, dict):
        raise api_error(400, "OTLP/JSON body must be a JSON object", hint="send an ExportTraceServiceRequest")
    spans: list[dict[str, Any]] = []
    for rs in payload.get("resourceSpans") or payload.get("resource_spans") or []:
        if not isinstance(rs, dict):
            continue
        resource = _attrs_json((rs.get("resource") or {}).get("attributes"))
        for ss in rs.get("scopeSpans") or rs.get("scope_spans") or []:
            if not isinstance(ss, dict):
                continue
            for span in ss.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                status = span.get("status") or {}
                code = status.get("code")
                is_error = code == 2 or (isinstance(code, str) and "ERROR" in code.upper())
                try:
                    start_ns = int(span.get("startTimeUnixNano") or span.get("start_time_unix_nano") or 0)
                    end_ns = int(span.get("endTimeUnixNano") or span.get("end_time_unix_nano") or 0)
                except (TypeError, ValueError):
                    start_ns = end_ns = 0
                spans.append(
                    _flat_span(
                        name=str(span.get("name") or ""),
                        trace_id=str(span.get("traceId") or span.get("trace_id") or ""),
                        parent_span_id=str(span.get("parentSpanId") or span.get("parent_span_id") or ""),
                        start_ns=start_ns,
                        end_ns=end_ns,
                        attrs=_attrs_json(span.get("attributes")),
                        is_error=is_error,
                        resource=resource,
                    )
                )
    return spans


def _parse_protobuf_body(body: bytes) -> list[dict[str, Any]]:
    req = ExportTraceServiceRequest()
    try:
        req.ParseFromString(body)
    except Exception:
        raise api_error(400, "malformed OTLP/protobuf body", hint="send an ExportTraceServiceRequest")
    spans: list[dict[str, Any]] = []
    for rs in req.resource_spans:
        resource = _attrs_pb(rs.resource.attributes)
        for ss in rs.scope_spans:
            for span in ss.spans:
                spans.append(
                    _flat_span(
                        name=span.name,
                        trace_id=span.trace_id.hex(),
                        parent_span_id=span.parent_span_id.hex(),
                        start_ns=int(span.start_time_unix_nano),
                        end_ns=int(span.end_time_unix_nano),
                        attrs=_attrs_pb(span.attributes),
                        is_error=span.status.code == 2,
                        resource=resource,
                    )
                )
    return spans


# ---------------------------------------------------------------- spans → session rows


def _agent_identity(resource: dict[str, Any]) -> str:
    for key in (_AGENT_ID_RESOURCE_ATTR, "service.name"):
        value = resource.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return DEFAULT_AGENT_ID


def _session_key(span: dict[str, Any]) -> str:
    sid = span["attrs"].get(_SESSION_ID_ATTR)
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    trace = span["trace_id"] or "unknown"
    return f"s_otlp_{trace[:12]}"


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _summarize(spans: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one session's spans from one batch."""
    agg: dict[str, Any] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "llm_calls": 0,
        "tool_calls": 0,
        "tool_errors": 0,
        "errors": 0,
        "model": None,
        "goal": None,
        "start_ns": None,
        "end_ns": None,
        "trace_id": None,
    }
    for span in spans:
        attrs = span["attrs"]
        kind = str(attrs.get(_OPENINFERENCE_KIND) or "").upper()
        if span["is_error"]:
            agg["errors"] += 1
        if span["start_ns"]:
            agg["start_ns"] = min(agg["start_ns"] or span["start_ns"], span["start_ns"])
        if span["end_ns"]:
            agg["end_ns"] = max(agg["end_ns"] or span["end_ns"], span["end_ns"])
        if agg["trace_id"] is None and span["trace_id"]:
            agg["trace_id"] = span["trace_id"]
        if kind == "LLM":
            agg["llm_calls"] += 1
            agg["input_tokens"] += _as_int(attrs.get("llm.token_count.prompt"))
            agg["output_tokens"] += _as_int(attrs.get("llm.token_count.completion"))
            agg["total_tokens"] += _as_int(attrs.get("llm.token_count.total"))
            model = attrs.get("llm.model_name")
            if isinstance(model, str) and model.strip():
                agg["model"] = model.strip()
        elif kind == "TOOL":
            agg["tool_calls"] += 1
            if span["is_error"]:
                agg["tool_errors"] += 1
        if kind in ("AGENT", "CHAIN") and not span["parent_span_id"].strip("0"):
            goal = attrs.get("input.value")
            if isinstance(goal, str) and goal.strip() and agg["goal"] is None:
                agg["goal"] = goal.strip()[:GOAL_EXCERPT_CHARS]
    if not agg["total_tokens"]:
        agg["total_tokens"] = agg["input_tokens"] + agg["output_tokens"]
    return agg


def _merge_session(
    conn: sqlite3.Connection,
    *,
    agent_id: str,
    session_id: str,
    agg: dict[str, Any],
) -> None:
    existing = repository.get_session(conn, session_id)
    prev = (existing or {}).get("usage") or {}
    if not isinstance(prev, dict):
        prev = {}
    usage = {
        "input_tokens": _as_int(prev.get("input_tokens")) + agg["input_tokens"],
        "output_tokens": _as_int(prev.get("output_tokens")) + agg["output_tokens"],
        "total_tokens": _as_int(prev.get("total_tokens")) + agg["total_tokens"],
        "llm_calls": _as_int(prev.get("llm_calls")) + agg["llm_calls"],
        "tool_calls": _as_int(prev.get("tool_calls")) + agg["tool_calls"],
        "tool_errors": _as_int(prev.get("tool_errors")) + agg["tool_errors"],
        "source": "otlp",
    }
    started_at = agg["start_ns"] // 1_000_000 if agg["start_ns"] else now_ms()
    ended_at = agg["end_ns"] // 1_000_000 if agg["end_ns"] else None
    if existing:
        started_at = min(_as_int(existing.get("started_at")) or started_at, started_at)
        prev_end = _as_int(existing.get("ended_at"))
        if prev_end and ended_at:
            ended_at = max(prev_end, ended_at)
        else:
            ended_at = ended_at or (prev_end or None)
    had_error = agg["errors"] > 0 or (existing or {}).get("status") == "error"
    repository.upsert_session(
        conn,
        {
            "session_id": session_id,
            "agent_id": agent_id,
            "scenario": (existing or {}).get("scenario"),
            "goal": agg["goal"] or (existing or {}).get("goal"),
            "model": agg["model"] or (existing or {}).get("model"),
            "status": "error" if had_error else "completed",
            "usage": usage,
            "trace_id": agg["trace_id"] or (existing or {}).get("trace_id"),
            "started_at": started_at,
            "ended_at": ended_at,
        },
    )


def ingest(conn: sqlite3.Connection, body: bytes, content_type: str) -> dict[str, Any]:
    """Parse one OTLP/HTTP export request and merge it into the fleet store."""
    if len(body) > MAX_BODY_BYTES:
        raise api_error(422, "OTLP body exceeds 4 MiB", hint="reduce the exporter batch size")
    if not body:
        raise api_error(400, "empty OTLP body", hint="send an ExportTraceServiceRequest")
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype == "application/json":
        spans = _parse_json_body(body)
    else:
        spans = _parse_protobuf_body(body)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for span in spans:
        key = (_agent_identity(span["resource"]), _session_key(span))
        grouped.setdefault(key, []).append(span)

    for (agent_id, session_id), session_spans in grouped.items():
        agg = _summarize(session_spans)
        repository.ensure_agent(conn, agent_id, exposure=None, model=agg["model"])
        conn.execute(
            "UPDATE agents SET last_seen=?, model=COALESCE(?, model) WHERE agent_id=?",
            (now_ms(), agg["model"], agent_id),
        )
        _merge_session(conn, agent_id=agent_id, session_id=session_id, agg=agg)
    conn.commit()
    return {
        "accepted_spans": len(spans),
        "sessions": len(grouped),
        "agents": len({agent for agent, _ in grouped}),
    }


def success_response_body() -> bytes:
    """Spec-shaped ExportTraceServiceResponse for protobuf clients."""
    return ExportTraceServiceResponse().SerializeToString()
