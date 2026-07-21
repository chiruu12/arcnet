from __future__ import annotations

import unittest
from types import SimpleNamespace

from arcnet.replay import ReplayCursor


class ReplayCursorTests(unittest.TestCase):
    def test_matches_by_name_and_records_skipped_steps(self) -> None:
        cursor = ReplayCursor(
            {
                "steps": [
                    {
                        "i": 0,
                        "type": "tool_call",
                        "tool": "lookup_customer",
                        "recorded_output": "customer",
                    },
                    {
                        "i": 1,
                        "type": "tool_call",
                        "tool": "fetch_url",
                        "recorded_output": "page",
                    },
                ]
            }
        )

        result = cursor(function_name="fetch_url", args={"url": "changed"})

        self.assertEqual(result, "page")
        self.assertEqual(cursor.cursor, 2)
        self.assertIn("skipped recorded lookup_customer", cursor.divergences[0]["note"])

    def test_unknown_tool_never_executes_real_function(self) -> None:
        cursor = ReplayCursor({"steps": []})

        result = cursor(
            function_name="send_email",
            args={"to": "nobody@example.com"},
            func=lambda **_: self.fail("real tool executed"),
        )

        self.assertEqual(result, "tool unavailable in replay")
        self.assertEqual(cursor.tool_errors, 1)

    def test_recorded_steer_applies_without_draining_live_queue(self) -> None:
        agent = SimpleNamespace(session_state={})
        live_queue = [{"kind": "kill", "reason": "must not apply"}]
        cursor = ReplayCursor(
            {
                "steps": [
                    {
                        "i": 0,
                        "type": "signal",
                        "kind": "steer",
                        "guidance": "prefer trusted tools only",
                    },
                    {
                        "i": 1,
                        "type": "tool_call",
                        "tool": "lookup_customer",
                        "recorded_output": "ok",
                    },
                ]
            }
        )

        result = cursor(function_name="lookup_customer", args={}, agent=agent)

        self.assertEqual(result, "ok")
        self.assertEqual(agent.session_state.get("arcnet_steer"), "prefer trusted tools only")
        self.assertFalse(agent.session_state.get("arcnet_kill"))
        self.assertEqual(live_queue, [{"kind": "kill", "reason": "must not apply"}])

    def test_recorded_kill_short_circuits_before_tool_stub(self) -> None:
        agent = SimpleNamespace(session_state={})
        cursor = ReplayCursor(
            {
                "steps": [
                    {
                        "i": 0,
                        "type": "tool_call",
                        "tool": "paginate_records",
                        "recorded_output": "page-1",
                    },
                    {"i": 1, "type": "signal", "kind": "kill", "reason": "token burn"},
                    {
                        "i": 2,
                        "type": "tool_call",
                        "tool": "paginate_records",
                        "recorded_output": "page-2",
                    },
                ]
            }
        )

        first = cursor(function_name="paginate_records", args={}, agent=agent)
        second = cursor(
            function_name="paginate_records",
            args={},
            agent=agent,
            func=lambda **_: self.fail("tool stub must not run after kill"),
        )

        self.assertEqual(first, "page-1")
        self.assertIn("KILLED", second)
        self.assertTrue(agent.session_state.get("arcnet_kill"))
        self.assertEqual(cursor.calls[-1]["result"], "kill")

    def test_recorded_pause_short_circuits_before_tool_stub(self) -> None:
        agent = SimpleNamespace(session_state={})
        cursor = ReplayCursor(
            {
                "steps": [
                    {"i": 0, "type": "signal", "kind": "pause", "reason": "HITL"},
                    {
                        "i": 1,
                        "type": "tool_call",
                        "tool": "run_query",
                        "recorded_output": "should-not-return",
                    },
                ]
            }
        )

        result = cursor(
            function_name="run_query",
            args={},
            agent=agent,
            func=lambda **_: self.fail("tool stub must not run while paused"),
        )

        self.assertIn("PAUSED", result)
        self.assertTrue(agent.session_state.get("arcnet_pause"))
        self.assertEqual(cursor.calls[-1]["result"], "pause")

    def test_recorded_kill_guard_on_tool_step(self) -> None:
        agent = SimpleNamespace(session_state={})
        cursor = ReplayCursor(
            {
                "steps": [
                    {
                        "i": 0,
                        "type": "tool_call",
                        "tool": "paginate_records",
                        "recorded_output": None,
                        "guard": {"checkpoint": "tool_call", "action": "kill"},
                    }
                ]
            }
        )

        result = cursor(function_name="paginate_records", args={}, agent=agent)

        self.assertIn("KILLED", result)
        self.assertTrue(agent.session_state.get("arcnet_kill"))
        self.assertEqual(cursor.calls[-1]["result"], "killed")


if __name__ == "__main__":
    unittest.main()
