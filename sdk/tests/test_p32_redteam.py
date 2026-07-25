"""P32 — SDK adversarial probes (canaries + tool-arg content scan)."""

from __future__ import annotations

import json
import time
import unittest

from unplug import Action

from arcnet.guard_factory import (
    TOOL_ARG_VALUE_SCAN_MAX,
    build_guard,
    canary_tokens,
    check_tool_call_with_content_guard,
    plant_canary_prompt,
    redact_canary_args,
    redact_canary_tokens,
)


class CanaryRedactionHardeningTests(unittest.TestCase):
    def test_nested_dict_canary_redacted(self) -> None:
        guard = build_guard()
        plant_canary_prompt(guard, "sys")
        token = canary_tokens(guard)[0]
        red = redact_canary_args({"payload": {"nested": {"deep": token}}}, guard)
        blob = json.dumps(red)
        self.assertNotIn(token, blob)
        self.assertIn("[REDACTED:canary]", blob)

    def test_nested_list_canary_redacted(self) -> None:
        guard = build_guard()
        plant_canary_prompt(guard, "sys")
        token = canary_tokens(guard)[0]
        red = redact_canary_args({"items": [token, "ok"]}, guard)
        blob = json.dumps(red)
        self.assertNotIn(token, blob)

    def test_split_canary_fragments_redacted(self) -> None:
        guard = build_guard()
        plant_canary_prompt(guard, "sys")
        token = canary_tokens(guard)[0]
        half = len(token) // 2
        red = redact_canary_args({"subject": token[:half], "body": token[half:]}, guard)
        blob = json.dumps(red)
        self.assertNotIn(token[:half], blob)
        self.assertNotIn(token[half:], blob)
        self.assertNotIn(token, blob)

    def test_many_canaries_redact_bounded_time(self) -> None:
        guard = build_guard()
        for i in range(50):
            plant_canary_prompt(guard, f"prompt{i}", label=f"l{i}")
        tokens = canary_tokens(guard)
        text = "x" * 10_000 + tokens[25] + "y" * 10_000
        t0 = time.perf_counter()
        out = redact_canary_tokens(text, guard)
        elapsed = time.perf_counter() - t0
        self.assertNotIn(tokens[25], out)
        self.assertLess(elapsed, 0.5, f"redaction took {elapsed:.2f}s")


class ToolArgContentScanHardeningTests(unittest.TestCase):
    def test_huge_payload_scan_bounded_time(self) -> None:
        guard = build_guard()
        huge = "A" * (2 * 1024 * 1024)
        t0 = time.perf_counter()
        result = check_tool_call_with_content_guard(
            guard,
            "send_email",
            {"body": huge, "to": "x@y.com"},
        )
        elapsed = time.perf_counter() - t0
        self.assertEqual(result.action, Action.ALLOW)
        self.assertLess(elapsed, 1.0, f"scan took {elapsed:.2f}s")

    def test_nested_dict_ssn_still_blocked(self) -> None:
        guard = build_guard()
        result = check_tool_call_with_content_guard(
            guard,
            "send_email",
            {"body": {"ssn": "123-45-6789"}, "to": "x@y.com"},
        )
        self.assertEqual(result.action, Action.BLOCK)

    def test_scan_cap_constant_matches_per_field_limit(self) -> None:
        guard = build_guard()
        pad = "z" * (TOOL_ARG_VALUE_SCAN_MAX + 100)
        secret = "ssn=123-45-6789"
        result = check_tool_call_with_content_guard(
            guard,
            "send_email",
            {"body": pad + secret, "to": "x@y.com"},
        )
        self.assertEqual(result.action, Action.ALLOW)


if __name__ == "__main__":
    unittest.main()
