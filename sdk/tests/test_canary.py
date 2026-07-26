"""F9 canary — plant, detect, and export-safety (hermetic, unplug-ai==0.6.0)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from unplug import Action, Guard, Source, TaintedText, TrustLevel

from arcnet.guard_factory import (
    build_guard,
    canary_tokens,
    plant_canary_prompt,
    redact_canary_args,
)
from arcnet.guardrail import output_post_hook, tool_call_middleware
from arcnet.init import init, shutdown


S1_PAGE = (
    __import__("pathlib").Path(__file__).resolve().parents[2]
    / "agents"
    / "scenarios"
    / "fixtures"
    / "shipping_poisoned.html"
)


class CanaryPlantTests(unittest.TestCase):
    def test_plant_canary_registers_unique_token(self) -> None:
        guard = build_guard()
        wrapped = plant_canary_prompt(guard, "You are Agent J")
        tokens = canary_tokens(guard)
        self.assertEqual(len(tokens), 1)
        self.assertIn(tokens[0], wrapped)
        self.assertTrue(wrapped.startswith("<!-- canary "))

    def test_plant_canary_fail_safe_on_error(self) -> None:
        guard = Guard()
        with patch.object(guard, "add_canary", side_effect=RuntimeError("boom")):
            out = plant_canary_prompt(guard, "plain prompt")
        self.assertEqual(out, "plain prompt")


class CanaryDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init(service_name="arcnet-canary-test", agent_id="agent_j", exposure="forward_facing")

    @classmethod
    def tearDownClass(cls) -> None:
        shutdown()

    def setUp(self) -> None:
        from arcnet.context import get_runtime

        rt = get_runtime()
        rt.guard = build_guard()
        rt.taint_sources.clear()
        rt.transcript = None

    def _plant(self) -> tuple[Guard, str]:
        from arcnet.context import get_runtime

        guard = get_runtime().guard
        plant_canary_prompt(guard, "system instructions")
        return guard, canary_tokens(guard)[0]

    def test_output_leak_produces_canary_threat(self) -> None:
        guard, token = self._plant()
        run_output = SimpleNamespace(content=f"My instructions were: {token}")
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value.status_code = 200
            output_post_hook(run_output)
            posts = mock_client.return_value.__enter__.return_value.post.call_args_list
        threat_posts = [c for c in posts if c.args and "/api/threats" in str(c.args[0])]
        self.assertTrue(threat_posts, "expected threat POST on canary output leak")
        payload = threat_posts[0].kwargs.get("json") or {}
        self.assertEqual(payload.get("subcategory"), "prompt_leak_canary")
        self.assertEqual(payload.get("pattern_class"), "canary")
        self.assertNotIn(token, json.dumps(payload))
        self.assertNotIn(token, run_output.content)

    def test_tool_argument_leak_produces_canary_threat(self) -> None:
        guard, token = self._plant()

        def _send(**_: object) -> str:
            return "EMAIL_SENT"

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value.status_code = 200
            out = tool_call_middleware(
                function_name="send_email",
                func=_send,
                args={"to": "user@corp.com", "subject": "x", "body": token},
                agent=SimpleNamespace(session_state={}),
            )
            posts = mock_client.return_value.__enter__.return_value.post.call_args_list
        self.assertIn("BLOCKED", str(out))
        threat_posts = [c for c in posts if c.args and "/api/threats" in str(c.args[0])]
        self.assertTrue(threat_posts)
        payload = threat_posts[0].kwargs.get("json") or {}
        self.assertEqual(payload.get("subcategory"), "prompt_leak_canary")
        self.assertNotIn(token, json.dumps(payload))

    def test_clean_run_emits_no_canary_threat(self) -> None:
        self._plant()
        run_output = SimpleNamespace(content="Order 4415 shipped yesterday.")
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value.status_code = 200
            output_post_hook(run_output)
            posts = mock_client.return_value.__enter__.return_value.post.call_args_list
        canary_posts = [
            c
            for c in posts
            if (c.kwargs.get("json") or {}).get("subcategory") == "prompt_leak_canary"
        ]
        self.assertFalse(canary_posts)

    def test_s1_taint_block_unchanged_with_canary_planted(self) -> None:
        from arcnet.guard_factory import check_tool_call_with_content_guard

        guard = build_guard()
        plant_canary_prompt(guard, "You are Agent J")
        page = S1_PAGE.read_text(encoding="utf-8")
        retrieved = guard.scan(page, source=Source.RETRIEVED)
        self.assertNotEqual(retrieved.action, Action.BLOCK)
        tainted = TaintedText(
            text=page, trust_level=TrustLevel.RETRIEVED, origin="fetch_url"
        )
        result = check_tool_call_with_content_guard(
            guard,
            "send_email",
            {
                "to": "edgar@bug-planet.net",
                "subject": "release confirmation",
                "body": "name=D. Edwards ssn=123-45-6789",
            },
            taint_sources=[tainted],
        )
        rules = {f.subcategory for f in (result.findings or [])}
        self.assertIn("retrieved_source_in_side_effect", rules)
        self.assertNotIn("prompt_leak_canary", rules)

    def test_transcript_args_redact_canary_before_persist(self) -> None:
        from arcnet.context import get_runtime
        from arcnet.transcript import TranscriptRecorder

        guard, token = self._plant()
        rt = get_runtime()
        rt.transcript = TranscriptRecorder(
            session_id="s_canary",
            agent_id="agent_j",
            goal="test",
            model="legacy-baseline-v1",
        )
        redacted = redact_canary_args({"body": token}, guard)
        rt.transcript.record_tool_call(
            tool="send_email",
            args=redacted,
            recorded_output=None,
            guard={"checkpoint": "tool_call", "action": "block"},
        )
        blob = json.dumps(rt.transcript.to_dict())
        self.assertNotIn(token, blob)


class CanaryExportSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "canary.db")
        import arcnet_server.main as m
        from arcnet_server.db import now_ms

        m._conn = None
        cls.m = m
        conn = m.get_conn()
        ts = now_ms()
        guard = build_guard()
        plant_canary_prompt(guard, "secret system prompt")
        token = canary_tokens(guard)[0]
        cls.canary_token = token
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "Agent J", "support/ops", "forward_facing", "legacy-baseline-v1", ts, ts),
        )
        transcript = {
            "session_id": "s_canary_export",
            "scenario": "canary",
            "goal": "test",
            "steps": [
                {
                    "i": 0,
                    "type": "tool_call",
                    "tool": "send_email",
                    "args": {"body": "[REDACTED:canary]"},
                    "guard": {
                        "checkpoint": "tool_call",
                        "action": "block",
                        "rule": "prompt_leak_canary",
                        "pattern_class": "canary",
                    },
                },
            ],
        }
        conn.execute(
            """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
               status, outcome, usage, trace_id, transcript, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "s_canary_export",
                "agent_j",
                "canary",
                "test",
                "legacy-baseline-v1",
                0.0,
                "failed",
                json.dumps({"goal_reached": "failed"}),
                json.dumps({}),
                "trace_canary",
                json.dumps(transcript),
                ts,
                ts,
            ),
        )
        conn.execute(
            """INSERT INTO threats (threat_id, session_id, agent_id, checkpoint, action, category,
               subcategory, risk_score, trust_level, evidence, trace_id, span_id, pattern_class, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "thr_canary",
                "s_canary_export",
                "agent_j",
                "output",
                "block",
                "leakage",
                "prompt_leak_canary",
                0.99,
                "tool_output",
                "Canary token for 'system_prompt' leaked into output",
                "trace_canary",
                "span1",
                "canary",
                ts,
            ),
        )
        conn.commit()

    def test_case_file_export_omits_canary_value(self) -> None:
        payload, md, env = self.m._case_file_zip_bytes("s_canary_export")
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            bundle = zf.read("case-file.json").decode() + zf.read("case-file.md").decode()
        self.assertNotIn(self.canary_token, bundle)
        self.assertIn("prompt_leak_canary", bundle)

    def test_agent_view_envelope_omits_canary_value(self) -> None:
        env = self.m.agent_view("threats", "s_canary_export")
        blob = json.dumps(env)
        self.assertNotIn(self.canary_token, blob)
        threats = env["data"].get("threats") or []
        self.assertTrue(any(t.get("subcategory") == "prompt_leak_canary" for t in threats))


if __name__ == "__main__":
    unittest.main()
