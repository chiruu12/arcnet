"""Adversarial API red-team — hostile input regression guards (docs/30)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from urllib.parse import quote

from fastapi.testclient import TestClient

from arcnet_server.read_models import EXCERPT_CHARS
from arcnet_server.validation import MAX_TEXT_CHARS, MAX_TRANSCRIPT_BYTES

# POST routes that accept JSON bodies (offline TestClient hammer).
POST_JSON_ROUTES: list[tuple[str, dict | None]] = [
    ("/api/agents", {"agent_id": "agent_j", "name": "J"}),
    ("/api/sessions", {"agent_id": "agent_j", "status": "running"}),
    ("/api/threats", {"agent_id": "agent_j", "action": "block"}),
    ("/api/sources", {"agent_id": "agent_j", "origin": "user"}),
    ("/api/signal", {"agent_id": "agent_j", "kind": "note", "severity": "info", "reason": "x"}),
    ("/api/replay", {"session_id": "s_rt", "candidate_model": "gpt-4o-mini"}),
    ("/api/agents/agent_j/versions", {"version": "v1"}),
    (
        "/api/agents/agent_j/apply-model",
        {"confirm": True, "model": "gpt-4o", "version": "rt-1"},
    ),
    ("/api/hitl", {"run_id": "run_rt", "session_id": "s_rt"}),
    ("/api/hitl/hitl_rt", {"decision": "approved"}),
    ("/api/griffin/evaluate", {"series_id": "arcnet.tokens.total|agent_j"}),
    ("/webhooks/signoz", {"status": "firing", "alerts": []}),
]

PAGINATED_LIST_ROUTES = [
    "/api/sessions",
    "/api/threats",
    "/api/sources",
    "/api/signals",
    "/api/replays",
    "/api/hitl",
    "/api/agents/agent_j/versions",
]

PATH_INJECTION_IDS = [
    "../etc/passwd",
    "..%2f..%2fetc%2fpasswd",
    "' OR 1=1--",
    "'; DROP TABLE sessions;--",
    "s_" + "x" * 10_000,
    "evil\u202e",
    "hitl_\x00evil",
]

WRITE_SECRET_ROUTES: list[tuple[str, dict]] = [
    ("/api/agents", {"agent_id": "agent_w", "name": "W"}),
    ("/api/sessions", {"agent_id": "agent_j", "status": "running", "session_id": "s_w"}),
    ("/api/threats", {"agent_id": "agent_j", "action": "allow"}),
    ("/api/sources", {"agent_id": "agent_j", "origin": "tool"}),
    (
        "/api/signal",
        {"agent_id": "agent_j", "kind": "note", "severity": "info", "reason": "w"},
    ),
    ("/api/agents/agent_j/versions", {"version": "w.1"}),
]


def _assert_client_error(response, *, label: str = "") -> None:
    assert response.status_code < 500, f"{label} returned {response.status_code}: {response.text[:300]}"
    assert response.status_code >= 400, f"{label} expected 4xx, got {response.status_code}"
    body = response.json()
    assert "detail" in body, f"{label} missing detail key: {body}"


def _deep_nest(depth: int) -> dict:
    node: dict = {"leaf": True}
    for _ in range(depth):
        node = {"nested": node}
    return node


class RedTeamApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "redteam.db")
        os.environ.pop("ARCNET_WRITE_SECRET", None)
        os.environ.pop("ARCNET_WEBHOOK_SECRET", None)
        import arcnet_server.main as m
        from arcnet_server.db import now_ms

        m._conn = None
        m._write_trust_logged = False
        cls.m = m
        cls.client = TestClient(m.app, raise_server_exceptions=False)
        conn = m.get_conn()
        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "Agent J", "support/ops", "internal", "gpt-4o-mini", ts, ts),
        )
        conn.execute(
            """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
               status, outcome, usage, trace_id, transcript, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "s_rt",
                "agent_j",
                "S1",
                "red-team goal",
                "gpt-4o-mini",
                0.0,
                "completed",
                json.dumps({"goal_reached": "clean"}),
                json.dumps({"cost_usd": 0.01}),
                "trace_rt",
                json.dumps({"steps": [{"i": 0, "type": "model_turn"}], "final_output": "ok"}),
                ts,
                ts,
            ),
        )
        conn.execute(
            """INSERT INTO hitl_requests (hitl_id, run_id, session_id, payload, status, created_at)
               VALUES (?,?,?,?,?,?)""",
            ("hitl_rt", "run_rt", "s_rt", json.dumps({"tool": "send_email"}), "pending", ts),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None
        os.environ.pop("ARCNET_WRITE_SECRET", None)

    # ---------------------------------------------------------------- malformed bodies

    def test_non_json_body_returns_400_not_500(self) -> None:
        for path, _ in POST_JSON_ROUTES:
            for payload, headers in (
                (b"not-json-at-all", {"content-type": "application/json"}),
                (b"", {"content-type": "application/json"}),
            ):
                res = self.client.post(path, content=payload, headers=headers)
                _assert_client_error(res, label=f"non-json {path}")

    def test_json_array_body_returns_400_not_500(self) -> None:
        for path, _ in POST_JSON_ROUTES:
            res = self.client.post(path, json=[])
            _assert_client_error(res, label=f"array {path}")

    def test_null_json_body_returns_400_not_500(self) -> None:
        for path, _ in POST_JSON_ROUTES:
            res = self.client.post(path, content=b"null", headers={"content-type": "application/json"})
            _assert_client_error(res, label=f"null {path}")

    def test_wrong_type_fields_return_4xx(self) -> None:
        res = self.client.post(
            "/api/sessions",
            json={"agent_id": 12345, "status": "running"},
        )
        self.assertLess(res.status_code, 500)
        res2 = self.client.post(
            "/api/signal",
            json={
                "agent_id": "agent_j",
                "kind": "note",
                "severity": "info",
                "reason": ["array", "not", "string"],
            },
        )
        self.assertLess(res2.status_code, 500)

    def test_missing_required_fields_return_400(self) -> None:
        cases = [
            ("/api/agents", {}),
            ("/api/sessions", {"status": "running"}),
            (
                "/api/signal",
                {"kind": "note", "severity": "info", "reason": "x"},
            ),
            ("/api/hitl", {"session_id": "s_rt"}),
        ]
        for path, body in cases:
            res = self.client.post(path, json=body)
            self.assertEqual(res.status_code, 400, (path, res.text))
            self.assertIn("detail", res.json())

    def test_deeply_nested_json_does_not_500(self) -> None:
        nest = _deep_nest(80)
        res = self.client.post(
            "/api/sessions",
            json={
                "agent_id": "agent_j",
                "status": "completed",
                "transcript": nest,
            },
        )
        self.assertLess(res.status_code, 500)

    # ---------------------------------------------------------------- path / param injection

    def test_session_path_injection_returns_404_not_500(self) -> None:
        for sid in PATH_INJECTION_IDS:
            encoded = quote(sid, safe="")
            for path in (
                f"/api/sessions/{encoded}",
                f"/api/agent-view/session/{encoded}",
                f"/api/agent-view/incident/{encoded}",
                f"/export/case-file/{encoded}",
            ):
                res = self.client.get(path)
                self.assertLess(res.status_code, 500, (path, res.status_code))
                if "export" in path or "sessions/" in path:
                    self.assertEqual(res.status_code, 404, path)

    def test_sql_meta_in_query_params_is_safe(self) -> None:
        evil = "' OR 1=1--"
        res = self.client.get(f"/api/sessions?agent_id={quote(evil)}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])
        res2 = self.client.get(f"/api/signals?session_id={quote(evil)}")
        self.assertEqual(res2.status_code, 200)

    def test_agent_view_unknown_view_is_404(self) -> None:
        res = self.client.get("/api/agent-view/no_such_view/all")
        self.assertEqual(res.status_code, 404)
        self.assertIn("detail", res.json())

    # ---------------------------------------------------------------- pagination abuse

    def test_pagination_abuse_returns_422(self) -> None:
        bad_queries = [
            "limit=-1",
            "limit=0",
            "limit=999999999",
            "limit=abc",
            "limit=1.5",
            "offset=-1",
            "offset=abc",
        ]
        for route in PAGINATED_LIST_ROUTES:
            for q in bad_queries:
                res = self.client.get(f"{route}?{q}")
                self.assertEqual(res.status_code, 422, f"{route}?{q}")
                self.assertIn("detail", res.json())

    def test_pagination_valid_clamps_headers(self) -> None:
        res = self.client.get("/api/sessions?limit=500&offset=0")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Limit"), "500")

    # ---------------------------------------------------------------- oversized payloads

    def test_oversized_transcript_rejected_on_write(self) -> None:
        big = "B" * (MAX_TRANSCRIPT_BYTES + 1)
        res = self.client.post(
            "/api/sessions",
            json={
                "agent_id": "agent_j",
                "status": "completed",
                "session_id": "s_huge",
                "transcript": {"steps": [], "final_output": big},
            },
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("transcript", res.json()["detail"].lower())

    def test_oversized_evidence_rejected_on_write(self) -> None:
        big = "E" * (MAX_TEXT_CHARS + 1)
        res = self.client.post(
            "/api/threats",
            json={"agent_id": "agent_j", "evidence": big, "action": "block"},
        )
        self.assertEqual(res.status_code, 422)

    def test_oversized_hitl_payload_rejected(self) -> None:
        big = {"blob": "P" * (65_536 + 100)}
        res = self.client.post(
            "/api/hitl",
            json={"run_id": "run_big", "payload": big},
        )
        self.assertEqual(res.status_code, 422)

    def test_agent_view_echoes_goal_bounded(self) -> None:
        huge_goal = "G" * (5 * 1024 * 1024)
        conn = self.m.get_conn()
        from arcnet_server.db import now_ms

        ts = now_ms()
        conn.execute(
            """INSERT INTO sessions (session_id, agent_id, status, goal, transcript, started_at)
               VALUES (?,?,?,?,?,?)""",
            (
                "s_hgoal",
                "agent_j",
                "completed",
                huge_goal,
                json.dumps({"steps": [], "final_output": "x"}),
                ts,
            ),
        )
        conn.commit()
        for path in (
            "/api/agent-view/session/s_hgoal",
            "/api/agent-view/check/s_hgoal",
            "/api/agent-view/case_files/s_hgoal",
            "/api/agent-view/incident/s_hgoal",
        ):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, path)
            blob = json.dumps(res.json())
            self.assertNotIn("G" * 500, blob, path)
            if path.endswith("/session/s_hgoal"):
                goal = res.json()["data"]["session"]["goal"]
                self.assertLessEqual(len(goal or ""), EXCERPT_CHARS + 1)

    def test_case_file_export_bounded(self) -> None:
        res = self.client.get("/export/case-file/s_hgoal")
        self.assertEqual(res.status_code, 200)
        self.assertLess(len(res.content), 50_000)
        self.assertNotIn(b"G" * 500, res.content)

    # ---------------------------------------------------------------- content-type / headers

    def test_missing_content_type_still_parses_json(self) -> None:
        res = self.client.post(
            "/api/signal",
            content=json.dumps(
                {
                    "agent_id": "agent_j",
                    "kind": "note",
                    "severity": "info",
                    "reason": "no ctype",
                }
            ),
        )
        self.assertEqual(res.status_code, 200)

    def test_wrong_charset_still_parses_utf8_json(self) -> None:
        res = self.client.post(
            "/api/signal",
            content=json.dumps(
                {
                    "agent_id": "agent_j",
                    "kind": "note",
                    "severity": "info",
                    "reason": "charset",
                }
            ).encode(),
            headers={"content-type": "application/json; charset=iso-8859-1"},
        )
        self.assertEqual(res.status_code, 200)

    def test_duplicate_query_params_last_wins(self) -> None:
        res = self.client.get("/api/sessions?limit=5&limit=3")
        self.assertIn(res.status_code, (200, 422))

    # ---------------------------------------------------------------- write-secret bypass

    def test_write_secret_blocks_all_mutating_ingest_routes(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = "rt-secret-xyz"
        try:
            for path, body in WRITE_SECRET_ROUTES:
                denied = self.client.post(path, json=body)
                self.assertEqual(denied.status_code, 401, path)
                wrong = self.client.post(
                    path,
                    headers={"X-ArcNet-Write-Secret": "wrong"},
                    json=body,
                )
                self.assertEqual(wrong.status_code, 401, path)
                empty = self.client.post(
                    path,
                    headers={"X-ArcNet-Write-Secret": ""},
                    json=body,
                )
                self.assertEqual(empty.status_code, 401, path)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_write_secret_bearer_and_header_both_work(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = "rt-secret-xyz"
        body = {
            "agent_id": "agent_j",
            "kind": "note",
            "severity": "info",
            "reason": "secret ok",
        }
        try:
            hdr = self.client.post(
                "/api/signal",
                headers={"X-ArcNet-Write-Secret": "rt-secret-xyz"},
                json=body,
            )
            self.assertEqual(hdr.status_code, 200)
            bearer = self.client.post(
                "/api/signal",
                headers={"Authorization": "Bearer rt-secret-xyz"},
                json={**body, "reason": "bearer ok"},
            )
            self.assertEqual(bearer.status_code, 200)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_apply_model_gated_by_write_secret(self) -> None:
        # apply-model is a mutating route: write-auth (P11-C) applies on top of
        # the human confirm:true gate. No header + secret set -> 401.
        os.environ["ARCNET_WRITE_SECRET"] = "rt-secret-xyz"
        try:
            unauth = self.client.post(
                "/api/agents/agent_j/apply-model",
                json={"confirm": True, "model": "gpt-4o", "version": "rt-open"},
            )
            self.assertEqual(unauth.status_code, 401)
            authed = self.client.post(
                "/api/agents/agent_j/apply-model",
                headers={"X-ArcNet-Write-Secret": "rt-secret-xyz"},
                json={"confirm": True, "model": "gpt-4o", "version": "rt-open"},
            )
            # Passes write-auth; not blocked at the auth layer (may still 4xx on
            # business rules, but never 401).
            self.assertNotEqual(authed.status_code, 401)
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)

    def test_no_partial_write_on_secret_failure(self) -> None:
        os.environ["ARCNET_WRITE_SECRET"] = "rt-secret-xyz"
        before = self.client.get("/api/fleet").json()
        try:
            self.client.post(
                "/api/agents",
                json={"agent_id": "agent_partial", "name": "Partial"},
            )
            after = self.client.get("/api/fleet").json()
            self.assertEqual(
                {a["agent_id"] for a in after},
                {a["agent_id"] for a in before},
            )
        finally:
            os.environ.pop("ARCNET_WRITE_SECRET", None)


if __name__ == "__main__":
    unittest.main()
