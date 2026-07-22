"""Wave A — session version filters, enriched pinpoint, write secret."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class WaveAVersionFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "wave_a.db")
        os.environ.pop("ARCNET_WRITE_SECRET", None)
        import arcnet_server.main as m
        from arcnet_server.db import now_ms

        m._conn = None
        m._write_trust_logged = False
        cls.m = m
        cls.client = TestClient(m.app)
        conn = m.get_conn()
        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "Agent J", "support/ops", "forward_facing", "gpt-4o-mini", ts, ts),
        )
        conn.execute(
            """INSERT INTO agent_versions
               (version_id, agent_id, version, model, model_version, source_ref, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                "av_wave_a",
                "agent_j",
                "wave-a.1",
                "gpt-4o-mini",
                None,
                "agents/prompts/agent_j.md",
                "baseline seed",
                ts,
            ),
        )
        for sid, model, pin in (
            ("s_pin_a", "gpt-4o-mini", "av_wave_a"),
            ("s_pin_b", "gpt-4o-mini", "av_wave_a"),
            ("s_other", "gpt-4o", None),
        ):
            conn.execute(
                """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
                   status, outcome, usage, trace_id, transcript, agent_version, started_at, ended_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    "agent_j",
                    "S1",
                    "goal",
                    model,
                    0.0,
                    "completed",
                    json.dumps({"goal_reached": "clean"}),
                    json.dumps({"cost_usd": 0.01}),
                    f"trace_{sid}",
                    None,
                    pin,
                    ts,
                    ts,
                ),
            )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None
        os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_sessions_filter_by_agent_version(self) -> None:
        res = self.client.get("/api/sessions?agent_id=agent_j&agent_version=av_wave_a")
        self.assertEqual(res.status_code, 200)
        rows = res.json()
        self.assertEqual({r["session_id"] for r in rows}, {"s_pin_a", "s_pin_b"})
        self.assertEqual(res.headers.get("X-Total-Count"), "2")

    def test_sessions_filter_by_version_id_alias(self) -> None:
        res = self.client.get("/api/sessions?agent_id=agent_j&version_id=av_wave_a&limit=1&offset=0")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.headers.get("X-Total-Count"), "2")
        self.assertEqual(res.headers.get("X-Limit"), "1")

    def test_version_filter_mismatch_is_400(self) -> None:
        res = self.client.get(
            "/api/sessions?agent_version=av_wave_a&version_id=av_other"
        )
        self.assertEqual(res.status_code, 400)

    def test_pinpoint_flat_fields_and_source_ref(self) -> None:
        check = self.client.get("/api/agent-view/check/s_pin_a").json()["data"]
        vp = check["version_pinpoint"]
        self.assertEqual(vp["version_id"], "av_wave_a")
        self.assertEqual(vp["version"], "wave-a.1")
        self.assertEqual(vp["model"], "gpt-4o-mini")
        self.assertEqual(vp["source_ref"], "agents/prompts/agent_j.md")
        self.assertTrue(vp["pinned_session_matches"])
        self.assertIn("source_ref=", vp["narrative"])

    def test_timeline_newest_first_ordering(self) -> None:
        older = self.client.post(
            "/api/agents/agent_j/versions",
            json={
                "version_id": "av_ord_1",
                "version": "older.1",
                "model": "gpt-4o-mini",
                "source_ref": "scripts/seed_demo.py",
            },
        )
        self.assertEqual(older.status_code, 200)
        # Distinct created_at — same-ms inserts tie-break by version_id.
        import time

        time.sleep(0.02)
        newer = self.client.post(
            "/api/agents/agent_j/versions",
            json={
                "version_id": "av_ord_2",
                "version": "newer.1",
                "model": "gpt-4o",
                "source_ref": "hq apply",
            },
        )
        self.assertEqual(newer.status_code, 200)
        tl = self.client.get("/api/agents/agent_j/versions/timeline").json()
        ids = [v["version_id"] for v in tl["versions"]]
        self.assertLess(ids.index("av_ord_2"), ids.index("av_ord_1"))
        self.assertIn("av_wave_a", ids)

    def test_apply_passthrough_source_ref(self) -> None:
        res = self.client.post(
            "/api/agents/agent_j/apply-model",
            json={
                "confirm": True,
                "model": "gpt-4o",
                "version": "apply-src.1",
                "source_ref": "git:deadbeef",
                "session_id": "s_other",
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["version"]["source_ref"], "git:deadbeef")
        check = self.client.get("/api/agent-view/check/s_other").json()["data"]
        self.assertEqual(check["version_pinpoint"]["source_ref"], "git:deadbeef")


class WaveAWriteSecretTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "write_secret.db")
        os.environ.pop("ARCNET_WRITE_SECRET", None)
        import arcnet_server.main as m

        m._conn = None
        m._write_trust_logged = False
        cls.m = m
        cls.client = TestClient(m.app)
        m.get_conn()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None
        os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_signal_open_when_secret_empty(self) -> None:
        os.environ.pop("ARCNET_WRITE_SECRET", None)
        res = self.client.post(
            "/api/signal",
            json={
                "agent_id": "agent_j",
                "kind": "note",
                "severity": "info",
                "reason": "open write",
                "source": "test",
            },
        )
        self.assertEqual(res.status_code, 200)

    def test_signal_requires_secret_when_set(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = "wave-a-secret"
        try:
            denied = self.client.post(
                "/api/signal",
                json={
                    "agent_id": "agent_j",
                    "kind": "note",
                    "severity": "info",
                    "reason": "blocked",
                    "source": "test",
                },
            )
            self.assertEqual(denied.status_code, 401)
            ok = self.client.post(
                "/api/signal",
                headers={"X-ArcNet-Write-Secret": "wave-a-secret"},
                json={
                    "agent_id": "agent_j",
                    "kind": "note",
                    "severity": "info",
                    "reason": "allowed",
                    "source": "test",
                },
            )
            self.assertEqual(ok.status_code, 200)
            bearer = self.client.post(
                "/api/signal",
                headers={"Authorization": "Bearer wave-a-secret"},
                json={
                    "agent_id": "agent_j",
                    "kind": "note",
                    "severity": "info",
                    "reason": "bearer ok",
                    "source": "test",
                },
            )
            self.assertEqual(bearer.status_code, 200)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)


if __name__ == "__main__":
    unittest.main()
