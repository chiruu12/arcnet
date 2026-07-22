"""Wave B — HQ tools reliability, Griffin MAD status, SigNoz evidence, model explore TM."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class WaveBApplyReloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmpdir.name) / "wave_b.db"
        os.environ["ARCNET_DB_PATH"] = str(cls.db_path)
        import arcnet_server.main as m

        m._conn = None
        cls.client = TestClient(m.app)
        cls.client.post(
            "/api/agents",
            json={"agent_id": "agent_j", "name": "J", "model": "gpt-4o-mini"},
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls._tmpdir.cleanup()

    def test_apply_model_sets_reload_required(self) -> None:
        ok = self.client.post(
            "/api/agents/agent_j/apply-model",
            json={"confirm": True, "model": "gpt-4o", "version": "wb-reload-1"},
        )
        self.assertEqual(ok.status_code, 200)
        body = ok.json()
        self.assertTrue(body["applied"])
        self.assertTrue(body["agentos_reload_required"])
        self.assertIn("AgentOS", body["agentos_reload_instructions"])


class WaveBGriffinStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmpdir.name) / "griffin.db"
        os.environ["ARCNET_DB_PATH"] = str(cls.db_path)
        cls.series_path = Path(cls._tmpdir.name) / "griffin_series.json"
        os.environ["ARCNET_GRIFFIN_SERIES"] = str(cls.series_path)
        import arcnet_server.main as m
        import arcnet_server.griffin as g

        m._conn = None
        g._CACHE.update(
            {
                "model": "mad",
                "estimator": "mad",
                "status": "cold",
                "series": {},
                "series_source": None,
                "last_cycle_ms": None,
                "last_evaluate_ms": None,
                "last_anomaly": None,
                "anomalies": [],
            }
        )
        cls.client = TestClient(m.app)
        cls.m = m
        # Seed a session with usage so sqlite_proxy can derive series
        t = 1_700_000_000_000
        conn = m.get_conn()
        conn.execute(
            "INSERT INTO agents(agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "J", "ops", "forward_facing", "gpt-4o-mini", t, t),
        )
        for i in range(35):
            usage = json.dumps({"total_tokens": 100 + i, "cost_usd": 0.01 * i, "tool_calls": i})
            conn.execute(
                "INSERT INTO sessions(session_id, agent_id, scenario, goal, model, temperature, "
                "status, outcome, usage, transcript, started_at, ended_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"s_wb_{i}",
                    "agent_j",
                    "S1",
                    "g",
                    "gpt-4o-mini",
                    0.0,
                    "completed",
                    "{}",
                    usage,
                    "{}",
                    t + i * 1000,
                    t + i * 1000,
                ),
            )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls._tmpdir.cleanup()

    def test_status_shape_mad_and_source(self) -> None:
        body = self.client.get("/api/griffin/status").json()
        self.assertEqual(body["estimator"], "mad")
        self.assertEqual(body["model"], "mad")
        self.assertIn(body["status"], ("cold", "warming", "ready"))
        self.assertIn("warmth", body)
        self.assertIn("honesty", body)
        self.assertIn("MAD", body["honesty"])
        self.assertNotIn("TabFM live", body.get("honesty", ""))
        self.assertIn(body.get("series_source"), ("sqlite_proxy", "seed", "none", None))


class WaveBSignozEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        os.environ["ARCNET_DB_PATH"] = str(Path(cls._tmpdir.name) / "sz.db")
        os.environ["SIGNOZ_API_KEY"] = ""
        os.environ["SIGNOZ_URL"] = "http://signoz.test"
        import arcnet_server.main as m

        m._conn = None
        cls.client = TestClient(m.app)
        cls.m = m
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
                "s_ev_1",
                "agent_j",
                "S1",
                "g",
                "gpt-4o-mini",
                0.0,
                "completed",
                "{}",
                json.dumps({"total_tokens": 42, "cost_usd": 0.01}),
                "{}",
                t,
                t,
                "trace_abc123",
            ),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls._tmpdir.cleanup()

    def test_evidence_without_key_is_honest(self) -> None:
        body = self.client.get("/api/signoz/evidence?session_id=s_ev_1").json()
        self.assertEqual(body["session_id"], "s_ev_1")
        self.assertEqual(body["trace_id"], "trace_abc123")
        self.assertFalse(body["api_key_present"])
        self.assertIn("signoz_trace", body["links"])
        self.assertTrue(body["links"]["signoz_trace"].endswith("/trace/trace_abc123"))
        self.assertIn("mcp_fallback", body)
        self.assertEqual(body["spans"], [])

    def test_evidence_missing_session_404(self) -> None:
        r = self.client.get("/api/signoz/evidence?session_id=s_missing")
        self.assertEqual(r.status_code, 404)

    def test_status_includes_mcp_note(self) -> None:
        with patch("arcnet_server.main.httpx.get") as g:
            resp = MagicMock()
            resp.status_code = 200
            g.return_value = resp
            body = self.client.get("/api/signoz/status").json()
        self.assertIn("mcp_note", body)
        self.assertIn("hang", body["mcp_note"].lower())


class WaveBHqToolsTests(unittest.TestCase):
    def test_get_timeout_returns_structured_error(self) -> None:
        from arcnet import hq_tools

        with patch("arcnet.hq_tools.httpx.Client") as client_cls:
            client = MagicMock()
            client_cls.return_value.__enter__.return_value = client
            client.get.side_effect = __import__("httpx").TimeoutException("boom")
            out = hq_tools._get("/api/fleet", tool="fleet_overview", retries=0)
        self.assertEqual(out["ok"], False)
        self.assertEqual(out["error"], "timeout")
        self.assertEqual(out["tool"], "fleet_overview")

    def test_propose_includes_evidence_refs(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_get") as g, patch.object(hq_tools, "_post") as p:
            g.return_value = {"model": "mad", "anomalies": [], "dashboards": {}}
            p.return_value = {
                "signal_id": "sig_p",
                "source": "hq_agent",
                "kind": "note",
            }
            out = hq_tools.propose_model_change(
                "agent_j",
                "gpt-4o",
                "upgrade",
                evidence_refs=["replay:r1", "griffin:arcnet.tokens.total|agent_j"],
            )
        self.assertTrue(out.get("ok"))
        self.assertIn("evidence_refs", out)
        self.assertIn("replay:r1", out["evidence_refs"])
        body = p.call_args[0][1]
        self.assertIn("evidence_refs=", body["guidance"])

    def test_apply_refuses_without_confirm(self) -> None:
        from arcnet import hq_tools

        out = hq_tools.apply_model_change("agent_j", "gpt-4o", "v1", confirm=False)
        self.assertFalse(out["applied"])
        self.assertEqual(out["ok"], False)
        self.assertFalse(out["agentos_reload_required"])


class WaveBModelExploreTests(unittest.TestCase):
    def test_compare_returns_evidence_refs(self) -> None:
        from arcnet.model_explore import compare_replay_verdicts

        with patch("httpx.Client") as client_cls:
            client = MagicMock()
            client_cls.return_value.__enter__.return_value = client
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = [
                {
                    "replay_id": "r_hero",
                    "candidate_model": "gpt-4o",
                    "verdict": {
                        "verdict": "better",
                        "confidence": "med",
                        "recommendation": "switch",
                        "baseline": {"model": "gpt-4o-mini", "resisted_injection": False},
                        "candidate": {
                            "model": "gpt-4o",
                            "resisted_injection": True,
                            "cost_usd": 0.02,
                        },
                    },
                }
            ]
            client.get.return_value = resp
            out = compare_replay_verdicts("s_ecfdb55d", server_url="http://test")
        self.assertTrue(out.get("ok"))
        self.assertTrue(any(r.startswith("replay:") for r in out["evidence_refs"]))
        self.assertIn("resisted_injection", out["dimension_winners"])

    def test_explore_loop_disabled_by_default(self) -> None:
        from arcnet.model_explore import maybe_run_explore_loop

        os.environ.pop("ARCNET_MODEL_EXPLORE_LOOP", None)
        out = maybe_run_explore_loop()
        self.assertFalse(out["ran"])
        self.assertTrue(out["exploration_only"])

    def test_explore_loop_recommend_only(self) -> None:
        from arcnet.model_explore import maybe_run_explore_loop

        os.environ["ARCNET_MODEL_EXPLORE_LOOP"] = "1"
        with tempfile.TemporaryDirectory() as td:
            os.environ["ARCNET_EXPLORE_DIR"] = td
            with patch("arcnet.model_explore.recommend_models") as rec:
                with patch("arcnet.model_explore.record_recommendation_note") as note:
                    rec.return_value = {
                        "recommendations": [{"model": "gpt-4o", "reason": "x", "evidence_refs": []}],
                        "exploration_only": True,
                    }
                    note.return_value = {"path": f"{td}/n.json"}
                    out = maybe_run_explore_loop(task_types=["tool_heavy"])
        os.environ.pop("ARCNET_MODEL_EXPLORE_LOOP", None)
        self.assertTrue(out["ran"])
        self.assertIn("never apply", out["note"])
        note.assert_called()
        # Ensure we never imported/called apply
        self.assertNotIn("apply", str(note.call_args).lower() + str(rec.call_args).lower())


class WaveBCheckTraceLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        os.environ["ARCNET_DB_PATH"] = str(Path(cls._tmpdir.name) / "check.db")
        os.environ["SIGNOZ_URL"] = "http://signoz.test"
        import arcnet_server.main as m

        m._conn = None
        cls.client = TestClient(m.app)
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
                "s_link",
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
                "tid_99",
            ),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls._tmpdir.cleanup()

    def test_check_and_incident_have_signoz_trace(self) -> None:
        check = self.client.get("/api/agent-view/check/s_link").json()
        self.assertEqual(check["links"]["signoz_trace"], "http://signoz.test/trace/tid_99")
        self.assertIn("evidence", check["hints"]["raw_evidence"].lower())
        incident = self.client.get("/api/agent-view/incident/s_link").json()
        self.assertEqual(incident["links"]["signoz_trace"], "http://signoz.test/trace/tid_99")


if __name__ == "__main__":
    unittest.main()
