"""SDK HQ session tools + model-explore (R2/R3)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class HqClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "hq_sdk.db")
        import arcnet_server.main as m
        from arcnet_server.db import now_ms

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app)
        conn = m.get_conn()
        t = now_ms()
        conn.execute(
            "INSERT INTO agents(agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_sdk", "SDK", "test", "internal", "gpt-4o-mini", t, t),
        )
        transcript = json.dumps(
            {
                "session_id": "s_sdk",
                "steps": [
                    {"i": 0, "type": "model_turn", "output_digest": "d"},
                    {
                        "i": 1,
                        "type": "tool_call",
                        "tool": "fetch_url",
                        "recorded_output": "SECRET" + ("x" * 200),
                    },
                ],
            }
        )
        conn.execute(
            "INSERT INTO sessions(session_id, agent_id, scenario, goal, model, temperature, status, "
            "outcome, usage, transcript, started_at, ended_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "s_sdk",
                "agent_sdk",
                "S1",
                "goal",
                "gpt-4o-mini",
                0.0,
                "completed",
                "{}",
                "{}",
                transcript,
                t,
                t,
            ),
        )
        conn.execute(
            "INSERT INTO signals(signal_id, session_id, agent_id, kind, severity, reason, "
            "evidence_link, guidance, source, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sig_sdk",
                "s_sdk",
                "agent_sdk",
                "steer",
                "high",
                "injection",
                None,
                "quarantine untrusted content",
                "guard",
                "active",
                t,
            ),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_sdk_check_and_signals_via_http(self) -> None:
        from arcnet.hq import check_session, signals_view

        # Point helpers at TestClient ASGI via monkeypatched httpx is heavy;
        # assert server envelopes + that SDK functions call the expected paths.
        with patch("arcnet.hq.httpx.Client") as client_cls:
            mock_client = MagicMock()
            client_cls.return_value.__enter__.return_value = mock_client
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"view": "check", "data": {"counts": {"signals": 1}}}
            mock_client.get.return_value = resp
            out = check_session("s_sdk", server_url="http://test")
            self.assertEqual(out["view"], "check")
            mock_client.get.assert_called_with("http://test/api/agent-view/check/s_sdk")

            resp.json.return_value = {"view": "signals", "data": {"signals": []}}
            signals_view("agent_sdk", server_url="http://test")
            mock_client.get.assert_called_with("http://test/api/agent-view/signals/agent_sdk")

        # Live envelope still has no recorded_output dumps
        body = self.client.get("/api/agent-view/check/s_sdk").json()
        dumped = json.dumps(body)
        self.assertNotIn("SECRET", dumped)
        self.assertNotIn("recorded_output", dumped)


class ModelExploreTests(unittest.TestCase):
    def test_list_and_recommend(self) -> None:
        from arcnet.model_explore import list_task_types, recommend_models, record_recommendation_note

        types = list_task_types()
        self.assertTrue(any(t["task_type"] == "injection_resist" for t in types))
        rec = recommend_models("injection_resist")
        self.assertTrue(rec["exploration_only"])
        self.assertGreaterEqual(len(rec["recommendations"]), 1)
        self.assertEqual(rec["recommendations"][0]["model"], "gpt-4o")
        with tempfile.TemporaryDirectory() as td:
            note = record_recommendation_note(
                task_type="injection_resist",
                recommendations=rec["recommendations"],
                out_dir=td,
            )
            self.assertTrue(Path(note["path"]).is_file())
            payload = json.loads(Path(note["path"]).read_text())
            self.assertEqual(payload["source"], "model_explorer")
            self.assertEqual(payload["kind"], "note")

    def test_catalog_snapshot_no_network(self) -> None:
        from arcnet.model_explore import fetch_provider_catalog

        cat = fetch_provider_catalog("openai", live=False)
        self.assertEqual(cat["source"], "snapshot")
        self.assertTrue(any(m["id"] == "gpt-4o" for m in cat["models"]))


class SignozDashboardMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "dash.db")
        import arcnet_server.main as m

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_env_dashboard_ids_on_status(self) -> None:
        os.environ["SIGNOZ_URL"] = "http://signoz.test"
        os.environ["SIGNOZ_API_KEY"] = ""
        os.environ["SIGNOZ_DASHBOARD_FLEET"] = "019f8883-fc38-test"
        os.environ.pop("SIGNOZ_DASHBOARD_THREATS", None)
        os.environ.pop("SIGNOZ_DASHBOARD_COST", None)
        os.environ.pop("SIGNOZ_DASHBOARD_AGNO", None)

        with patch("arcnet_server.main.httpx.get") as g:
            resp = MagicMock()
            resp.status_code = 200
            g.return_value = resp
            body = self.client.get("/api/signoz/status").json()
        self.assertEqual(body["dashboards"]["fleet_ops"], "019f8883-fc38-test")
        self.assertIsNone(body["dashboards"]["threats_trust"])

    def test_title_resolve_fills_missing(self) -> None:
        os.environ["SIGNOZ_URL"] = "http://signoz.test"
        os.environ["SIGNOZ_API_KEY"] = "k"
        for k in (
            "SIGNOZ_DASHBOARD_FLEET",
            "SIGNOZ_DASHBOARD_THREATS",
            "SIGNOZ_DASHBOARD_COST",
            "SIGNOZ_DASHBOARD_AGNO",
        ):
            os.environ.pop(k, None)

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "/api/v1/dashboards" in str(url):
                resp.json.return_value = {
                    "data": [
                        {
                            "id": "id-fleet",
                            "data": {"title": "ArcNet Fleet Ops"},
                        },
                        {
                            "id": "id-threats",
                            "data": {"title": "ArcNet Threats & Trust"},
                        },
                    ]
                }
            return resp

        with patch("arcnet_server.main.httpx.get", side_effect=fake_get):
            with patch("arcnet_server.main.httpx.post") as post:
                pr = MagicMock()
                pr.status_code = 200
                post.return_value = pr
                body = self.client.get("/api/signoz/status").json()
        self.assertEqual(body["dashboards"]["fleet_ops"], "id-fleet")
        self.assertEqual(body["dashboards"]["threats_trust"], "id-threats")


if __name__ == "__main__":
    unittest.main()
