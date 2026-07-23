"""HITL create → list → decide smoke (docs/12 / P6-A)."""

from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class HitlApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "hitl.db")
        import arcnet_server.main as m

        m._conn = None
        cls.client = TestClient(m.app)

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


if __name__ == "__main__":
    unittest.main()
