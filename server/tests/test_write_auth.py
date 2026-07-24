"""Coherent optional write auth — every mutating route (docs/12 P11-C)."""

from __future__ import annotations

import hmac
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from arcnet_server.write_auth import WRITE_SECRET_HEADER

SECRET = "p11c-write-secret"
AUTH_HEADER = {WRITE_SECRET_HEADER: SECRET}

# Mutating routes gated by ARCNET_WRITE_SECRET (not webhook).
WRITE_ROUTES: list[tuple[str, str, dict]] = [
    ("POST", "/api/agents", {"agent_id": "agent_w", "name": "Write Auth Agent"}),
    ("POST", "/api/sessions", {"agent_id": "agent_w", "status": "running"}),
    (
        "POST",
        "/api/threats",
        {
            "agent_id": "agent_w",
            "checkpoint": "input",
            "action": "allow",
            "category": "test",
        },
    ),
    (
        "POST",
        "/api/sources",
        {
            "agent_id": "agent_w",
            "origin": "user",
            "trust_level": "user",
            "scan_action": "allow",
        },
    ),
    (
        "POST",
        "/api/signal",
        {
            "agent_id": "agent_w",
            "kind": "note",
            "severity": "info",
            "reason": "write auth probe",
            "source": "test",
        },
    ),
    ("POST", "/api/agents/agent_w/versions", {"version": "wa.1"}),
    (
        "POST",
        "/api/agents/agent_w/apply-model",
        {"confirm": True, "model": "gpt-4o-mini", "version": "wa.apply"},
    ),
    ("POST", "/api/replay", {"session_id": "s_missing", "candidate_model": "gpt-4o"}),
    ("POST", "/api/hitl", {"run_id": "run_wa", "session_id": "s_wa"}),
    ("POST", "/api/hitl/hitl_missing", {"decision": "approved"}),
    (
        "POST",
        "/api/griffin/evaluate",
        {"series_id": "arcnet.tokens.total|agent_w", "observed": 42.0},
    ),
]

READ_ROUTES = [
    "/health",
    "/api/fleet",
    "/api/sessions",
    "/api/threats",
    "/api/sources",
    "/api/signals",
    "/api/replays",
    "/api/hitl",
    "/api/griffin/status",
    "/api/signoz/status",
    "/api/agent-view/home/all",
]


class WriteAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "write_auth.db")
        os.environ.pop("ARCNET_WRITE_SECRET", None)
        os.environ.pop("ARCNET_WEBHOOK_SECRET", None)
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
            ("agent_w", "Write Auth Agent", "ops", "internal", "gpt-4o-mini", ts, ts),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None
        os.environ.pop("ARCNET_WRITE_SECRET", None)
        os.environ.pop("ARCNET_WEBHOOK_SECRET", None)

    def setUp(self) -> None:
        os.environ.pop("ARCNET_WRITE_SECRET", None)

    def _post(self, path: str, json_body: dict, *, headers: dict | None = None) -> object:
        return self.client.post(path, json=json_body, headers=headers or {})

    def test_writes_open_when_secret_unset(self) -> None:
        for _method, path, body in WRITE_ROUTES:
            with self.subTest(path=path):
                res = self._post(path, body)
                self.assertNotEqual(
                    res.status_code,
                    401,
                    f"{path} should not require write secret when unset",
                )

    def test_reads_always_open_with_secret_set(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = SECRET
        try:
            for path in READ_ROUTES:
                with self.subTest(path=path):
                    res = self.client.get(path)
                    self.assertNotEqual(res.status_code, 401, path)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_mutating_routes_401_without_secret_when_set(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = SECRET
        try:
            for _method, path, body in WRITE_ROUTES:
                with self.subTest(path=path):
                    res = self._post(path, body)
                    self.assertEqual(res.status_code, 401, res.text)
                    payload = res.json()
                    self.assertIn("detail", payload)
                    self.assertIn("hint", payload)
                    self.assertIn("write secret", payload["detail"].lower())
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_mutating_routes_401_with_wrong_secret(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = SECRET
        bad = {WRITE_SECRET_HEADER: "wrong-secret"}
        try:
            for _method, path, body in WRITE_ROUTES:
                with self.subTest(path=path):
                    res = self._post(path, body, headers=bad)
                    self.assertEqual(res.status_code, 401)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_mutating_routes_succeed_with_correct_secret(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = SECRET
        try:
            for _method, path, body in WRITE_ROUTES:
                with self.subTest(path=path):
                    res = self._post(path, body, headers=AUTH_HEADER)
                    self.assertNotEqual(res.status_code, 401, res.text)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_bearer_token_accepted(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = SECRET
        try:
            res = self.client.post(
                "/api/signal",
                headers={"Authorization": f"Bearer {SECRET}"},
                json={
                    "agent_id": "agent_w",
                    "kind": "note",
                    "severity": "info",
                    "reason": "bearer ok",
                    "source": "test",
                },
            )
            self.assertEqual(res.status_code, 200)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_compare_digest_used_for_write_secret(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = SECRET
        try:
            with patch.object(hmac, "compare_digest", wraps=hmac.compare_digest) as mocked:
                res = self._post(
                    "/api/signal",
                    {
                        "agent_id": "agent_w",
                        "kind": "note",
                        "severity": "info",
                        "reason": "digest probe",
                        "source": "test",
                    },
                    headers=AUTH_HEADER,
                )
                self.assertEqual(res.status_code, 200)
                self.assertTrue(mocked.called)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_webhook_uses_webhook_secret_not_write_secret(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = SECRET
        os.environ["ARCNET_WEBHOOK_SECRET"] = "webhook-only"
        try:
            denied_write_header = self.client.post(
                "/webhooks/signoz",
                headers=AUTH_HEADER,
                json={},
            )
            self.assertEqual(denied_write_header.status_code, 401)

            ok = self.client.post(
                "/webhooks/signoz",
                headers={"X-ArcNet-Webhook-Secret": "webhook-only"},
                json={},
            )
            self.assertEqual(ok.status_code, 204)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)
            os.environ.pop("ARCNET_WEBHOOK_SECRET", None)

    def test_hitl_decide_with_auth(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = SECRET
        try:
            created = self._post(
                "/api/hitl",
                {"run_id": "run_decide", "session_id": "s_wa", "payload": {}},
                headers=AUTH_HEADER,
            )
            self.assertEqual(created.status_code, 200)
            hitl_id = created.json()["hitl_id"]
            decided = self._post(
                f"/api/hitl/{hitl_id}",
                {"decision": "approved"},
                headers=AUTH_HEADER,
            )
            self.assertEqual(decided.status_code, 200)
            self.assertEqual(decided.json()["status"], "approved")
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)


if __name__ == "__main__":
    unittest.main()
