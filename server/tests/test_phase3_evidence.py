"""Phase 3 — SigNoz Query Range golden fixtures + dashboard UUID distinctness.

No live SigNoz cloud required.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class QueryRangeGoldenFixtureTests(unittest.TestCase):
    def test_span_like_fixture_extracts_real_spans(self) -> None:
        from arcnet_server.main import _extract_bounded_spans

        body = _load("query_range_span_like.json")
        spans = _extract_bounded_spans(body, max_spans=8)
        names = [s["name"] for s in spans]
        self.assertEqual(
            names,
            ["hello_arcnet.run", "OpenAIChat.invoke", "add"],
        )
        self.assertTrue(all("duration_ns" in s for s in spans))
        # Metadata column / query names must not appear as spans
        self.assertNotIn("A", names)
        self.assertNotIn("name", names)
        self.assertNotIn("durationNano", names)

    def test_non_span_metrics_fixture_yields_no_spans(self) -> None:
        from arcnet_server.main import _extract_bounded_spans

        body = _load("query_range_non_span.json")
        spans = _extract_bounded_spans(body, max_spans=8)
        self.assertEqual(
            spans,
            [],
            "metrics/matrix Query Range shape must not invent span rows",
        )

    def test_mixed_fixture_keeps_span_like_only(self) -> None:
        from arcnet_server.main import _extract_bounded_spans

        body = _load("query_range_mixed.json")
        spans = _extract_bounded_spans(body, max_spans=8)
        names = [s["name"] for s in spans]
        self.assertIn("agent_j.run", names)
        self.assertIn("tool.fetch_url", names)
        self.assertNotIn("column_label_only", names)
        self.assertNotIn("query_meta_only", names)
        self.assertNotIn("spanName", names)

    def test_evidence_endpoint_uses_extractor_on_fixture_shape(self) -> None:
        """Wire golden body through /api/signoz/evidence without live cloud."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ["ARCNET_DB_PATH"] = str(Path(tmp.name) / "ev.db")
        os.environ["SIGNOZ_API_KEY"] = "test-key"
        os.environ["SIGNOZ_URL"] = "http://signoz.test"
        import arcnet_server.main as m

        m._conn = None
        client = TestClient(m.app)
        self.addCleanup(client.close)
        t = 1_700_000_000_000
        conn = m.get_conn()
        conn.execute(
            "INSERT INTO agents(agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "J", "ops", "internal", "gpt-4o-mini", t, t),
        )
        conn.execute(
            "INSERT INTO sessions(session_id, agent_id, scenario, goal, model, temperature, "
            "status, outcome, usage, transcript, started_at, ended_at, trace_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "s_fx_1",
                "agent_j",
                "S1",
                "g",
                "gpt-4o-mini",
                0.0,
                "completed",
                "{}",
                "{}",
                "{}",
                t,
                t,
                "68a0c4a9b793b111882557834a98f57b",
            ),
        )
        conn.commit()

        golden = _load("query_range_span_like.json")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = golden
        with patch("arcnet_server.main.httpx.post", return_value=mock_resp):
            body = client.get("/api/signoz/evidence?session_id=s_fx_1").json()
        self.assertTrue(body.get("query_ok"))
        names = [s["name"] for s in body["spans"]]
        self.assertIn("hello_arcnet.run", names)
        self.assertIn("MCP", body["mcp_fallback"])
        self.assertIn("Query Range", body["mcp_fallback"])


class SignozDashboardUuidDistinctTests(unittest.TestCase):
    """A1 residual: provisioned status → ≥3 distinct dashboard UUIDs."""

    def test_env_overrides_are_distinct(self) -> None:
        from arcnet_server.main import _signoz_dashboard_map

        with patch.dict(
            os.environ,
            {
                "SIGNOZ_DASHBOARD_FLEET": "019f8883-fc38-7000-8000-000000000001",
                "SIGNOZ_DASHBOARD_THREATS": "019f8883-fc4a-7000-8000-000000000002",
                "SIGNOZ_DASHBOARD_COST": "019f8883-fc57-7000-8000-000000000003",
                "SIGNOZ_DASHBOARD_AGNO": "019f8883-fc67-7000-8000-000000000004",
            },
            clear=False,
        ):
            out = _signoz_dashboard_map("http://signoz.test", key="")
        ids = [v for v in out.values() if v]
        self.assertGreaterEqual(len(ids), 3)
        self.assertEqual(len(ids), len(set(ids)), "dashboard UUIDs must be distinct")

    def test_list_api_fills_distinct_titles(self) -> None:
        from arcnet_server.main import _signoz_dashboard_map

        for k in (
            "SIGNOZ_DASHBOARD_FLEET",
            "SIGNOZ_DASHBOARD_THREATS",
            "SIGNOZ_DASHBOARD_COST",
            "SIGNOZ_DASHBOARD_AGNO",
        ):
            os.environ.pop(k, None)
        payload = {
            "data": [
                {"id": "uuid-fleet", "data": {"title": "ArcNet Fleet Ops"}},
                {"id": "uuid-threats", "data": {"title": "ArcNet Threats & Trust"}},
                {"id": "uuid-cost", "data": {"title": "ArcNet Cost & Tokens"}},
                {"id": "uuid-agno", "data": {"title": "Agno"}},
                {"id": "uuid-other", "data": {"title": "Unrelated"}},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        with patch("arcnet_server.main.httpx.get", return_value=mock_resp):
            out = _signoz_dashboard_map("http://signoz.test", key="k")
        ids = [v for v in out.values() if v]
        self.assertGreaterEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(out["fleet_ops"], "uuid-fleet")
        self.assertEqual(out["agno"], "uuid-agno")


class McpHangPrefersHttpHintsTests(unittest.TestCase):
    def test_agent_view_hints_name_http_before_mcp(self) -> None:
        from arcnet_server.read_models import envelope

        env = envelope(
            "check",
            "s_hint",
            {"ok": True},
            trace_id="tid_1",
            human_view="/#case_files",
        )
        raw = env["hints"]["raw_evidence"]
        http_idx = raw.lower().find("/api/signoz/evidence")
        mcp_idx = raw.lower().find("mcp")
        self.assertGreaterEqual(http_idx, 0)
        self.assertGreaterEqual(mcp_idx, 0)
        self.assertLess(
            http_idx,
            mcp_idx,
            "HTTP/Query Range evidence must be preferred before MCP in hints",
        )


if __name__ == "__main__":
    unittest.main()
