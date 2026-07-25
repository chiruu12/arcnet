"""P32 — Griffin MAD edge-case probes."""

from __future__ import annotations

import math
import unittest

from arcnet_server.griffin import mad_judge, tabfm_enabled


class GriffinEdgeCaseTests(unittest.TestCase):
    def test_identical_samples_mad_zero_no_crash(self) -> None:
        vals = [100.0] * 40
        result = mad_judge(vals)
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["outlier"])
        self.assertIsNotNone(result.get("mad"))

    def test_nan_observed_does_not_fire_outlier(self) -> None:
        vals = [1.0] * 40
        result = mad_judge(vals, observed=float("nan"))
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["outlier"])
        self.assertIsNone(result.get("z"))

    def test_inf_observed_does_not_fire_outlier(self) -> None:
        vals = [1.0] * 40
        result = mad_judge(vals, observed=float("inf"))
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["outlier"])
        self.assertIsNone(result.get("z"))

    def test_tabfm_disabled_by_default(self) -> None:
        self.assertFalse(tabfm_enabled())


if __name__ == "__main__":
    unittest.main()
