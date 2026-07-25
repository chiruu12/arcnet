"""HITL create → list → decide smoke (docs/12 / P6-A) + decide relay (P21)."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class HitlApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "hitl.db")
        os.environ["ARCNET_AGENTOS_URL"] = ""  # explicitly disable relay HTTP
        import arcnet_server.main as m

        m._conn = None
        cls.client = TestClient(m.app)

    def setUp(self) -> None:
        os.environ["ARCNET_AGENTOS_URL"] = ""  # explicitly disable relay HTTP

    def test_create_list_decide_status_flips(self) -> None:
        created = self.client.post(
            "/api/hitl",
            json={
                "run_id": "run_smoke",
                "session_id": "s_hitl_smoke",
                "payload": {"reason": "tool call needs approval", "tool": "send_email"},
            },
        )
        self.assertEqual(created.status_code, 200)
        body = created.json()
        hitl_id = body["hitl_id"]
        self.assertTrue(hitl_id.startswith("hitl_"))
        self.assertEqual(body["status"], "pending")

        listed = self.client.get("/api/hitl?status=pending")
        self.assertEqual(listed.status_code, 200)
        rows = listed.json()
        self.assertTrue(any(r["hitl_id"] == hitl_id for r in rows))
        self.assertEqual(listed.headers.get("X-Total-Count"), "1")

        approved = self.client.post(f"/api/hitl/{hitl_id}", json={"decision": "approved"})
        self.assertEqual(approved.status_code, 200)
        decided = approved.json()
        self.assertEqual(decided["status"], "approved")
        self.assertIsNotNone(decided.get("decided_at"))
        relay = decided.get("relay")
        self.assertIsInstance(relay, dict)
        self.assertFalse(relay["attempted"])
        self.assertFalse(relay["delivered"])

        pending = self.client.get("/api/hitl?status=pending").json()
        self.assertFalse(any(r["hitl_id"] == hitl_id for r in pending))

        rejected_req = self.client.post(
            "/api/hitl",
            json={"run_id": "run_reject", "session_id": "s_hitl_smoke", "payload": {"reason": "x"}},
        ).json()
        rejected = self.client.post(
            f"/api/hitl/{rejected_req['hitl_id']}",
            json={"decision": "rejected"},
        ).json()
        self.assertEqual(rejected["status"], "rejected")

    def test_decide_invalid_returns_400(self) -> None:
        created = self.client.post(
            "/api/hitl",
            json={"run_id": "run_bad", "session_id": "s_bad", "payload": {}},
        ).json()
        bad = self.client.post(f"/api/hitl/{created['hitl_id']}", json={"decision": "maybe"})
        self.assertEqual(bad.status_code, 400)

    def _seed_session(self, session_id: str = "s_hitl_relay") -> str:
        self.client.post(
            "/api/agents",
            json={"agent_id": "agent_j", "name": "J", "model": "gpt-4o-mini"},
        )
        self.client.post(
            "/api/sessions",
            json={
                "session_id": session_id,
                "agent_id": "agent_j",
                "scenario": "S1",
                "goal": "hitl relay",
                "model": "gpt-4o-mini",
                "status": "running",
            },
        )
        return session_id

    def _mock_relay_client(
        self,
        *,
        status_code: int = 200,
        stream_error: Exception | None = None,
    ) -> MagicMock:
        class _Stream:
            def __init__(self, code: int) -> None:
                self.status_code = code

            async def aiter_bytes(self):
                yield b""

        stream_ctx = MagicMock()
        if stream_error is not None:
            stream_ctx.__aenter__ = AsyncMock(side_effect=stream_error)
        else:
            stream_ctx.__aenter__ = AsyncMock(return_value=_Stream(status_code))
        stream_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=stream_ctx)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        return mock_client

    def test_relay_success_posts_kill_signal(self) -> None:
        sid = self._seed_session()
        hitl_id = self.client.post(
            "/api/hitl",
            json={"run_id": "run_kill", "session_id": sid, "payload": {"reason": "stop"}},
        ).json()["hitl_id"]

        mock_client = self._mock_relay_client(status_code=200)

        with patch.dict(os.environ, {"ARCNET_AGENTOS_URL": "http://agentos.test:7777"}):
            with patch("arcnet_server.hitl_relay.httpx.AsyncClient", return_value=mock_client):
                res = self.client.post(f"/api/hitl/{hitl_id}", json={"decision": "rejected"})

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "rejected")
        relay = body["relay"]
        self.assertTrue(relay["attempted"])
        self.assertTrue(relay["delivered"])

        signals = self.client.get(f"/api/signals?session_id={sid}&limit=10").json()
        self.assertTrue(any(s.get("kind") == "kill" and s.get("source") == "hitl" for s in signals))

    def test_relay_failure_still_persists_decision(self) -> None:
        sid = self._seed_session("s_hitl_fail")
        hitl_id = self.client.post(
            "/api/hitl",
            json={"run_id": "run_fail", "session_id": sid, "payload": {}},
        ).json()["hitl_id"]

        mock_client = self._mock_relay_client(status_code=503)

        with patch.dict(os.environ, {"ARCNET_AGENTOS_URL": "http://agentos.test:7777"}):
            with patch("arcnet_server.hitl_relay.httpx.AsyncClient", return_value=mock_client):
                res = self.client.post(f"/api/hitl/{hitl_id}", json={"decision": "rejected"})

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "rejected")
        relay = body["relay"]
        self.assertTrue(relay["attempted"])
        self.assertFalse(relay["delivered"])
        self.assertIn("503", relay["detail"])

        row = self.client.get("/api/hitl?status=rejected").json()
        self.assertTrue(any(r["hitl_id"] == hitl_id for r in row))

    def test_relay_timeout_still_persists_decision(self) -> None:
        import httpx

        sid = self._seed_session("s_hitl_timeout")
        hitl_id = self.client.post(
            "/api/hitl",
            json={"run_id": "run_timeout", "session_id": sid, "payload": {}},
        ).json()["hitl_id"]

        mock_client = self._mock_relay_client(stream_error=httpx.TimeoutException("timed out"))

        with patch.dict(os.environ, {"ARCNET_AGENTOS_URL": "http://agentos.test:7777"}):
            with patch("arcnet_server.hitl_relay.httpx.AsyncClient", return_value=mock_client):
                res = self.client.post(f"/api/hitl/{hitl_id}", json={"decision": "approved"})

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "approved")
        relay = body["relay"]
        self.assertTrue(relay["attempted"])
        self.assertFalse(relay["delivered"])
        self.assertIn("timeout", relay["detail"].lower())

        signals = self.client.get(f"/api/signals?session_id={sid}&limit=10").json()
        self.assertTrue(any(s.get("kind") == "note" and s.get("source") == "hitl" for s in signals))


if __name__ == "__main__":
    unittest.main()
