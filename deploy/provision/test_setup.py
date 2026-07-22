"""Unit tests for deploy/provision/setup.py helpers (no SigNoz required)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from setup import (  # noqa: E402
    DASHBOARDS,
    EPHEMERAL_PROBE_ALERTS,
    _dashboard_title,
    _duplicate_ids_to_delete,
    _managed_dashboard_titles,
    _payload_dashboard_title,
)


class PayloadDashboardTitleTests(unittest.TestCase):
    def test_top_level_title(self) -> None:
        self.assertEqual(_payload_dashboard_title({"title": "ArcNet Fleet Ops"}), "ArcNet Fleet Ops")

    def test_nested_data_title(self) -> None:
        self.assertEqual(
            _payload_dashboard_title({"data": {"title": "Agno", "widgets": []}}),
            "Agno",
        )

    def test_missing_title(self) -> None:
        self.assertIsNone(_payload_dashboard_title({"widgets": []}))


class ApiDashboardTitleTests(unittest.TestCase):
    def test_list_item_nested_title(self) -> None:
        item = {"id": "abc", "data": {"title": "ArcNet Cost & Tokens"}}
        self.assertEqual(_dashboard_title(item), "ArcNet Cost & Tokens")

    def test_list_item_double_nested_title(self) -> None:
        item = {"id": "abc", "data": {"data": {"title": "Agno"}}}
        self.assertEqual(_dashboard_title(item), "Agno")


class ManagedDedupeTests(unittest.TestCase):
    def test_managed_titles_match_dashboard_files(self) -> None:
        titles = _managed_dashboard_titles()
        self.assertEqual(len(titles), len(DASHBOARDS))
        self.assertIn("ArcNet Fleet Ops", titles)
        self.assertIn("Agno", titles)

    def test_dedupe_skips_unowned_titles(self) -> None:
        managed = frozenset({"ArcNet Fleet Ops"})
        title_to_ids = {
            "ArcNet Fleet Ops": ["keep", "drop-managed"],
            "Shared Ops": ["user-a", "user-b"],
        }
        extras = _duplicate_ids_to_delete(title_to_ids, managed)
        self.assertEqual(extras, [("ArcNet Fleet Ops", "drop-managed")])

    def test_dedupe_noop_when_unique(self) -> None:
        managed = frozenset({"Agno"})
        self.assertEqual(_duplicate_ids_to_delete({"Agno": ["only"]}, managed), [])


class ProbeCleanupTests(unittest.TestCase):
    def test_exact_ephemeral_names_only(self) -> None:
        self.assertEqual(
            EPHEMERAL_PROBE_ALERTS,
            frozenset({"arcnet probe", "arcnet seasonal probe"}),
        )
        # Prefix would match a legitimate-looking name; exact set must not.
        self.assertTrue("arcnet probe latency".startswith("arcnet probe"))
        for name in (
            "arcnet probe latency",
            "arcnet.threats.detected > 0",
            "arcnet agent p99 latency",
        ):
            self.assertNotIn(name, EPHEMERAL_PROBE_ALERTS)


if __name__ == "__main__":
    unittest.main()
