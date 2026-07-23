"""P9-A — API coherence: every route exercised; pagination + structured errors."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import zipfile

from fastapi.testclient import TestClient


def _seed(conn) -> None:
    from arcnet_server.db import now_ms

    ts = now_ms()
    conn.execute(
        "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?)",
        ("agent_j", "Agent J", "support", "forward_facing", "gpt-4o-mini", ts, ts),
    )
    conn.execute(
        """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, status,
           trace_id, transcript, started_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            "s_coherence",
            "agent_j",
            "S1",
            "ship order",
            "gpt-4o-mini",
            "failed",
            "trace_coherence",
            json.dumps({"steps": [], "final_output": "blocked"}),
            ts,
        ),
    )
    conn.execute(
        """INSERT INTO threats (threat_id, session_id, agent_id, checkpoint, action,
           category, risk_score, evidence, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        ("thr_coh", "s_coherence", "agent_j", "tool_call", "block", "leakage", 0.9, "exfil", ts),
    )
    conn.execute(
        """INSERT INTO sources (source_id, session_id, agent_id, origin, trust_level,
           scan_action, findings, created_at) VALUES (?,?,?,?,?,?,?,?)""",
        ("src_coh", "s_coherence", "agent_j", "http://example.test", "retrieved", "allow", 0, ts),
    )
    conn.execute(
        """INSERT INTO signals (signal_id, session_id, agent_id, kind, severity,
           reason, source, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        ("sig_coh", "s_coherence", "agent_j", "note", "info", "ping", "inline", "pending", ts),
    )
    conn.execute(
        """INSERT INTO replays (replay_id, session_id, candidate_model, runs, verdict,
           created_at, duration_ms) VALUES (?,?,?,?,?,?,?)""",
        (
            "r_coherence",
            "s_coherence",
            "gpt-4o",
            json.dumps([]),
            json.dumps({"recommendation": "promote candidate", "overall": "better"}),
            ts,
            900,
        ),
    )
    conn.commit()


class ApiCoherenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "coherence.db")
        import arcnet_server.main as m

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app)
        _seed(m.get_conn())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_health(self) -> None:
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_write_ingest_roundtrip(self) -> None:
        agent = self.client.post(
            "/api/agents",
            json={"agent_id": "agent_x", "name": "X", "exposure": "internal"},
        )
        self.assertEqual(agent.status_code, 200)
        session = self.client.post(
            "/api/sessions",
            json={
                "session_id": "s_ingest",
                "agent_id": "agent_x",
                "status": "completed",
            },
        )
        self.assertEqual(session.status_code, 200)
        threat = self.client.post(
            "/api/threats",
            json={"session_id": "s_ingest", "agent_id": "agent_x", "action": "block"},
        )
        self.assertEqual(threat.status_code, 200)
        source = self.client.post(
            "/api/sources",
            json={"session_id": "s_ingest", "agent_id": "agent_x", "origin": "user"},
        )
        self.assertEqual(source.status_code, 200)
        signal = self.client.post(
            "/api/signal",
            json={
                "session_id": "s_ingest",
                "agent_id": "agent_x",
                "kind": "note",
                "severity": "info",
                "reason": "coherence",
                "source": "manual",
            },
        )
        self.assertEqual(signal.status_code, 200)

    def test_list_pagination_headers(self) -> None:
        cases = [
            ("/api/threats?limit=1&offset=0", "1", "1"),
            ("/api/sources?limit=1&offset=0", "1", "1"),
            ("/api/replays?session_id=s_coherence&limit=1&offset=0", "1", "1"),
            ("/api/hitl?limit=10&offset=0", "0", "10"),
        ]
        for path, total_key, limit_hdr in cases:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn("X-Total-Count", r.headers, path)
            self.assertEqual(r.headers.get("X-Limit"), limit_hdr, path)
            self.assertEqual(r.headers.get("X-Offset"), "0", path)
            self.assertEqual(r.headers.get("X-Total-Count"), total_key, path)

    def test_export_case_file_http(self) -> None:
        r = self.client.get("/export/case-file/s_coherence")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("content-type"), "application/zip")
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            self.assertEqual(set(zf.namelist()), {"case-file.md", "case-file.json"})
            env = json.loads(zf.read("case-file.json"))
        self.assertEqual(env["view"], "incident")
        self.assertEqual(env["id"], "s_coherence")

    def test_replay_agent_view_route(self) -> None:
        r = self.client.get("/api/agent-view/replay/r_coherence")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["view"], "replay")
        self.assertEqual(body["id"], "r_coherence")
        self.assertIn("overall", body["data"])
        missing = self.client.get("/api/agent-view/replay/r_missing")
        self.assertEqual(missing.status_code, 404)
        err = missing.json()
        self.assertIn("detail", err)
        self.assertIn("hint", err)

    def test_model_intel_404_structured(self) -> None:
        r = self.client.get("/api/agents/nobody/model-intel")
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertIn("detail", body)
        self.assertIn("hint", body)
        self.assertIn("/api/fleet", body["hint"])

    def test_hitl_decide_404_structured(self) -> None:
        r = self.client.post("/api/hitl/hitl_missing", json={"decision": "approved"})
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertIn("detail", body)
        self.assertIn("hint", body)

    def test_apply_model_agent_404_structured(self) -> None:
        r = self.client.post(
            "/api/agents/nobody/apply-model",
            json={"confirm": True, "model": "gpt-4o", "version": "v1"},
        )
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertIn("detail", body)
        self.assertIn("hint", body)

    def test_griffin_evaluate(self) -> None:
        r = self.client.post(
            "/api/griffin/evaluate",
            json={"series_id": "arcnet.tokens.total|agent_j", "observed": 42.0},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("series_id", body)
        self.assertIn("outlier", body)

    def test_signals_stream_reconnect_contract(self) -> None:
        """SSE Last-Event-ID replay dumps the same rows as GET /api/signals (docs/12)."""
        paths = [getattr(r, "path", "") for r in self.m.app.routes]
        self.assertIn("/signals/stream", paths)
        api_ids = {
            row["signal_id"]
            for row in self.client.get("/api/signals?session_id=s_coherence&limit=50").json()
        }
        conn = self.m.get_conn()
        db_ids = {
            row[0]
            for row in conn.execute(
                "SELECT signal_id FROM signals WHERE session_id=? ORDER BY created_at DESC LIMIT 50",
                ("s_coherence",),
            ).fetchall()
        }
        self.assertEqual(api_ids, db_ids)
        self.assertIn("sig_coh", api_ids)


if __name__ == "__main__":
    unittest.main()
