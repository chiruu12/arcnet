"""SDK pricing vs server model_catalog — same model id must agree."""

from __future__ import annotations

import unittest

from arcnet.pricing import PRICES, cost_usd


class PricingAlignmentTests(unittest.TestCase):
    def _catalog(self):
        from arcnet_server import model_catalog

        return model_catalog

    def test_shared_model_ids_match_catalog_mtok_rates(self) -> None:
        model_catalog = self._catalog()
        shared = [mid for mid in PRICES if model_catalog.get_model(mid) is not None]
        self.assertIn("gpt-4o-mini", shared)
        self.assertIn("gpt-4o", shared)
        for model_id in shared:
            inp_per_1k, out_per_1k = PRICES[model_id]
            row = model_catalog.get_model(model_id)
            assert row is not None
            self.assertAlmostEqual(
                float(row["input_usd_per_mtok"]),
                inp_per_1k * 1000.0,
                places=8,
                msg=f"{model_id} input rate mismatch",
            )
            self.assertAlmostEqual(
                float(row["output_usd_per_mtok"]),
                out_per_1k * 1000.0,
                places=8,
                msg=f"{model_id} output rate mismatch",
            )

    def test_cost_usd_matches_catalog_projection(self) -> None:
        model_catalog = self._catalog()
        for model_id in PRICES:
            if model_catalog.get_model(model_id) is None:
                continue
            sdk = cost_usd(model_id, 12_345, 6_789)
            catalog = model_catalog.project_cost_usd(
                model_id, input_tokens=12_345, output_tokens=6_789
            )
            self.assertIsNotNone(catalog)
            self.assertAlmostEqual(sdk, catalog or 0.0, places=10)


if __name__ == "__main__":
    unittest.main()
