"""Corpus scorecard and fleet latency aggregates."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from arcnet_server.corpus_service import (
    CORPUS_MAX_SESSIONS,
    stored_corpus_scorecard,
)
from arcnet_server.db import now_ms
from arcnet_server.repository import fleet_latency_24h


def _verdict(
    *,
    session_id: str,
    verdict_name: str = "improved",
    baseline_goal: str = "failed",
    candidate_goal: str = "clean",
    b_cost: float = 0.01,
    c_cost: float = 0.005,
    b_steps: int = 5,
    c_steps: int = 3,
    scenario: str = "S4",
    resisted: bool | None = None,
) -> dict:
    baseline: dict = {
        "model": "baseline",
        "goal_reached": baseline_goal,
        "steps": b_steps,
        "cost_usd": b_cost,
    }
    candidate: dict = {
        "model": "candidate",
        "goal_reached": candidate_goal,
        "steps": c_steps,
        "cost_usd": c_cost,
    }
    if resisted is not None:
        baseline["exfil_attempts"] = 0 if resisted else 1
        candidate["resisted_injection"] = resisted
        candidate["exfil_attempts"] = 0 if resisted else 1
    return {
        "replay_id": f"r_{session_id}",
        "session_id": session_id,
        "scenario": scenario,
        "baseline": baseline,
        "candidate": candidate,
        "verdict": verdict_name,
        "confidence": "3/3 runs",
        "recommendation": "test",
    }


class FleetLatencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(self._tmp, "latency.db")
        import arcnet_server.main as m

        m._conn = None
        self.m = m
        self.client = TestClient(m.app)
        self.conn = m.get_conn()
        ts = now_ms()
        self.conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "Agent J", "ops", "internal", "legacy-baseline-v1", ts, ts),
        )
        # Wall-clock samples: 1000ms and 3000ms
        self.conn.execute(
            """INSERT INTO sessions
               (session_id, agent_id, status, usage, started_at, ended_at)
               VALUES (?,?,?,?,?,?)""",
            ("s_l1", "agent_j", "completed", json.dumps({"latency_ms": 9999}), ts - 1000, ts),
        )
        self.conn.execute(
            """INSERT INTO sessions
               (session_id, agent_id, status, usage, started_at, ended_at)
               VALUES (?,?,?,?,?,?)""",
            ("s_l2", "agent_j", "completed", None, ts - 4000, ts - 1000),
        )
        # usage-only fallback when ended_at missing
        self.conn.execute(
            """INSERT INTO sessions
               (session_id, agent_id, status, usage, started_at, ended_at)
               VALUES (?,?,?,?,?,?)""",
            (
                "s_l3",
                "agent_j",
                "completed",
                json.dumps({"latency_ms": 2000}),
                ts - 2000,
                None,
            ),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.m._conn = None

    def test_fleet_latency_from_recorded_wall_clock(self) -> None:
        day_ago = now_ms() - 24 * 60 * 60 * 1000
        lat = fleet_latency_24h(self.conn, day_ago=day_ago)
        agent = lat["agent_j"]
        self.assertEqual(agent["latency_sample_count_24h"], 3)
        self.assertEqual(agent["p50_wall_clock_ms_24h"], 2000.0)
        self.assertEqual(agent["p95_wall_clock_ms_24h"], 2900.0)
        self.assertIn("ended_at-started_at", agent["latency_source_24h"])

    def test_fleet_api_exposes_latency_fields(self) -> None:
        row = self.client.get("/api/fleet").json()[0]
        health = row["health"]
        self.assertIn("p50_wall_clock_ms_24h", health)
        self.assertIn("p95_wall_clock_ms_24h", health)
        self.assertEqual(health["latency_sample_count_24h"], 3)
        self.assertIsNotNone(health["latency_source_24h"])


class CorpusScorecardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(self._tmp, "corpus.db")
        import arcnet_server.main as m

        m._conn = None
        self.m = m
        self.client = TestClient(m.app)
        self.conn = m.get_conn()
        ts = now_ms()
        self.conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "Agent J", "ops", "internal", "legacy-baseline-v1", ts, ts),
        )
        for sid, verdict_name, resisted in (
            ("s_c1", "improved", None),
            ("s_c2", "regressed", True),
            ("s_c3", "mixed", False),
        ):
            self.conn.execute(
                "INSERT INTO sessions (session_id, agent_id, status, transcript) VALUES (?,?,?,?)",
                (sid, "agent_j", "failed", json.dumps({"steps": []})),
            )
            verdict = _verdict(
                session_id=sid,
                verdict_name=verdict_name,
                resisted=resisted,
                scenario="S1" if resisted is not None else "S4",
            )
            self.conn.execute(
                """INSERT INTO replays
                   (replay_id, session_id, candidate_model, candidate_prompt_ref,
                    runs, verdict, created_at, duration_ms)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    f"r_{sid}",
                    sid,
                    "gpt-4o",
                    None,
                    json.dumps([]),
                    json.dumps(verdict),
                    ts,
                    1200,
                ),
            )
        self.conn.commit()

    def tearDown(self) -> None:
        self.m._conn = None

    def test_stored_mode_aggregates_verdicts_offline(self) -> None:
        out = stored_corpus_scorecard(self.conn)
        self.assertEqual(out["mode"], "stored")
        self.assertEqual(out["session_count"], 3)
        self.assertEqual(out["verdict_counts"]["improved"], 1)
        self.assertEqual(out["verdict_counts"]["regressed"], 1)
        self.assertEqual(out["verdict_counts"]["mixed"], 1)
        self.assertEqual(out["goals_reached"]["baseline"], 0)
        self.assertEqual(out["goals_reached"]["candidate"], 3)
        self.assertLess(out["cost_delta_usd_total"], 0)
        self.assertEqual(out["threat_resistance"]["threat_sessions"], 2)
        self.assertEqual(out["threat_resistance"]["candidate_resisted"], 1)

    def test_stored_http_mode_default(self) -> None:
        res = self.client.post("/api/replay/corpus", json={})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["mode"], "stored")
        self.assertEqual(body["session_count"], 3)

    def test_session_cap_rejected(self) -> None:
        ids = [f"s_x{i}" for i in range(CORPUS_MAX_SESSIONS + 1)]
        res = self.client.post("/api/replay/corpus", json={"session_ids": ids})
        self.assertEqual(res.status_code, 400)
        self.assertIn(str(CORPUS_MAX_SESSIONS), res.json()["detail"])

    def test_live_mode_requires_candidate_model(self) -> None:
        res = self.client.post("/api/replay/corpus", json={"mode": "live"})
        self.assertEqual(res.status_code, 400)

    def test_live_mode_uses_execute_replay(self) -> None:
        run_payload = {
            "model": "gpt-4o",
            "goal_reached": "clean",
            "steps": 2,
            "tool_errors": 0,
            "cost_usd": 0.004,
            "latency_ms": 5000,
            "tokens": 400,
            "divergences": [],
        }
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = run_payload
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("arcnet_server.replay_service.httpx.AsyncClient", return_value=mock_client):
            res = self.client.post(
                "/api/replay/corpus",
                json={
                    "mode": "live",
                    "candidate_model": "gpt-4o",
                    "session_ids": ["s_c1"],
                },
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["mode"], "live")
        self.assertEqual(body["session_count"], 1)
        self.assertEqual(body["candidate_model"], "gpt-4o")
        self.assertEqual(mock_client.post.await_count, 3)


if __name__ == "__main__":
    unittest.main()
