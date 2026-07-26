"""OTLP/HTTP ingest — any OpenInference framework lands in the fleet (offline)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)


def _kv(key: str, value: object) -> dict[str, object]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        # protobuf JSON mapping encodes int64 as strings
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _json_export(
    *,
    service_name: str = "support-bot",
    resource_extra: list[dict[str, object]] | None = None,
    spans: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [_kv("service.name", service_name)] + (resource_extra or [])
                },
                "scopeSpans": [{"spans": spans}],
            }
        ]
    }


def _span(
    *,
    name: str,
    trace_id: str = "aa11bb22cc33dd44ee55ff6677889900",
    parent: str = "",
    kind: str = "AGENT",
    start_ns: int = 1_000_000_000_000,
    end_ns: int = 2_000_000_000_000,
    attrs: list[dict[str, object]] | None = None,
    error: bool = False,
) -> dict[str, object]:
    span: dict[str, object] = {
        "traceId": trace_id,
        "spanId": "0102030405060708",
        "parentSpanId": parent,
        "name": name,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": [_kv("openinference.span.kind", kind)] + (attrs or []),
    }
    if error:
        span["status"] = {"code": 2}
    return span


class OtlpIngestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "otlp.db")
        os.environ.pop("ARCNET_WRITE_SECRET", None)
        import arcnet_server.main as m

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app, raise_server_exceptions=False)

    def _post_json(self, payload: dict[str, object]) -> object:
        return self.client.post(
            "/v1/traces",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_json_export_creates_agent_and_session(self) -> None:
        payload = _json_export(
            spans=[
                _span(
                    name="agent.run",
                    kind="AGENT",
                    attrs=[
                        _kv("session.id", "s_otlp_case1"),
                        _kv("input.value", "summarize the ticket backlog"),
                    ],
                ),
                _span(
                    name="llm.invoke",
                    kind="LLM",
                    parent="0102030405060708",
                    attrs=[
                        _kv("session.id", "s_otlp_case1"),
                        _kv("llm.model_name", "gpt-4o-mini"),
                        _kv("llm.token_count.prompt", 120),
                        _kv("llm.token_count.completion", 40),
                        _kv("llm.token_count.total", 160),
                    ],
                ),
                _span(
                    name="tool.search",
                    kind="TOOL",
                    parent="0102030405060708",
                    attrs=[_kv("session.id", "s_otlp_case1")],
                ),
            ]
        )
        res = self._post_json(payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["arcnet"]["accepted_spans"], 3)

        conn = self.m.get_conn()
        from arcnet_server import repository

        agent = repository.get_agent(conn, "support-bot")
        assert agent is not None
        self.assertEqual(agent["model"], "gpt-4o-mini")

        session = repository.get_session(conn, "s_otlp_case1")
        assert session is not None
        self.assertEqual(session["agent_id"], "support-bot")
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["goal"], "summarize the ticket backlog")
        usage = session["usage"]
        self.assertEqual(usage["input_tokens"], 120)
        self.assertEqual(usage["output_tokens"], 40)
        self.assertEqual(usage["total_tokens"], 160)
        self.assertEqual(usage["llm_calls"], 1)
        self.assertEqual(usage["tool_calls"], 1)
        self.assertEqual(usage["source"], "otlp")
        self.assertEqual(session["started_at"], 1_000_000)
        self.assertEqual(session["ended_at"], 2_000_000)

    def test_second_batch_accumulates_into_same_session(self) -> None:
        base = _json_export(
            spans=[
                _span(
                    name="llm.invoke",
                    kind="LLM",
                    attrs=[
                        _kv("session.id", "s_otlp_merge"),
                        _kv("llm.token_count.prompt", 10),
                        _kv("llm.token_count.completion", 5),
                    ],
                )
            ]
        )
        self.assertEqual(self._post_json(base).status_code, 200)
        second = _json_export(
            spans=[
                _span(
                    name="llm.invoke",
                    kind="LLM",
                    start_ns=3_000_000_000_000,
                    end_ns=4_000_000_000_000,
                    attrs=[
                        _kv("session.id", "s_otlp_merge"),
                        _kv("llm.token_count.prompt", 7),
                        _kv("llm.token_count.completion", 3),
                    ],
                )
            ]
        )
        self.assertEqual(self._post_json(second).status_code, 200)

        from arcnet_server import repository

        session = repository.get_session(self.m.get_conn(), "s_otlp_merge")
        assert session is not None
        self.assertEqual(session["usage"]["input_tokens"], 17)
        self.assertEqual(session["usage"]["output_tokens"], 8)
        self.assertEqual(session["usage"]["llm_calls"], 2)
        self.assertEqual(session["started_at"], 1_000_000)
        self.assertEqual(session["ended_at"], 4_000_000)

    def test_trace_id_fallback_when_no_session_attr(self) -> None:
        payload = _json_export(
            spans=[
                _span(name="agent.run", trace_id="11111111111111111111111111111111"),
                _span(name="agent.run", trace_id="22222222222222222222222222222222"),
            ]
        )
        res = self._post_json(payload)
        self.assertEqual(res.json()["arcnet"]["sessions"], 2)

        from arcnet_server import repository

        conn = self.m.get_conn()
        self.assertIsNotNone(repository.get_session(conn, "s_otlp_111111111111"))
        self.assertIsNotNone(repository.get_session(conn, "s_otlp_222222222222"))

    def test_error_status_marks_session_and_tool_errors(self) -> None:
        payload = _json_export(
            spans=[
                _span(
                    name="tool.exec",
                    kind="TOOL",
                    error=True,
                    attrs=[_kv("session.id", "s_otlp_err")],
                )
            ]
        )
        self.assertEqual(self._post_json(payload).status_code, 200)

        from arcnet_server import repository

        session = repository.get_session(self.m.get_conn(), "s_otlp_err")
        assert session is not None
        self.assertEqual(session["status"], "error")
        self.assertEqual(session["usage"]["tool_errors"], 1)

    def test_agent_id_resource_attr_overrides_service_name(self) -> None:
        payload = _json_export(
            service_name="ignored-name",
            resource_extra=[_kv("arcnet.agent_id", "my-crew")],
            spans=[_span(name="agent.run", attrs=[_kv("session.id", "s_otlp_crew")])],
        )
        self.assertEqual(self._post_json(payload).status_code, 200)

        from arcnet_server import repository

        session = repository.get_session(self.m.get_conn(), "s_otlp_crew")
        assert session is not None
        self.assertEqual(session["agent_id"], "my-crew")

    def test_protobuf_export_accepted(self) -> None:
        req = ExportTraceServiceRequest()
        rs = req.resource_spans.add()
        attr = rs.resource.attributes.add()
        attr.key = "service.name"
        attr.value.string_value = "pb-bot"
        ss = rs.scope_spans.add()
        span = ss.spans.add()
        span.name = "agent.run"
        span.trace_id = bytes.fromhex("ab" * 16)
        span.span_id = bytes.fromhex("cd" * 8)
        span.start_time_unix_nano = 5_000_000_000_000
        span.end_time_unix_nano = 6_000_000_000_000
        kind = span.attributes.add()
        kind.key = "openinference.span.kind"
        kind.value.string_value = "AGENT"
        res = self.client.post(
            "/v1/traces",
            content=req.SerializeToString(),
            headers={"Content-Type": "application/x-protobuf"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/x-protobuf")
        self.assertEqual(res.headers["X-Arcnet-Accepted-Spans"], "1")

        from arcnet_server import repository

        self.assertIsNotNone(repository.get_agent(self.m.get_conn(), "pb-bot"))

    def test_malformed_bodies_rejected(self) -> None:
        res = self.client.post(
            "/v1/traces", content=b"not json", headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("hint", res.json())

        res = self.client.post(
            "/v1/traces", content=b"", headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 400)

        res = self.client.post(
            "/v1/traces",
            content=b"\x00garbage-protobuf",
            headers={"Content-Type": "application/x-protobuf"},
        )
        self.assertEqual(res.status_code, 400)

    def test_oversize_body_rejected(self) -> None:
        res = self.client.post(
            "/v1/traces",
            content=b"x" * (4 * 1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(res.status_code, 422)

    def test_ingested_agent_visible_in_fleet(self) -> None:
        payload = _json_export(
            service_name="fleet-bot",
            spans=[_span(name="agent.run", attrs=[_kv("session.id", "s_otlp_fleet")])],
        )
        self.assertEqual(self._post_json(payload).status_code, 200)
        fleet = self.client.get("/api/fleet").json()
        self.assertIn("fleet-bot", [a["agent_id"] for a in fleet])


class OtlpWriteAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "otlp_auth.db")
        os.environ["ARCNET_WRITE_SECRET"] = "otlp-secret"
        import arcnet_server.main as m

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls) -> None:
        os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_secret_required_when_configured(self) -> None:
        payload = json.dumps(_json_export(spans=[_span(name="agent.run")]))
        res = self.client.post(
            "/v1/traces", content=payload, headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 401)

        res = self.client.post(
            "/v1/traces",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Arcnet-Write-Secret": "otlp-secret",
            },
        )
        self.assertEqual(res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
