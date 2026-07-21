from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
