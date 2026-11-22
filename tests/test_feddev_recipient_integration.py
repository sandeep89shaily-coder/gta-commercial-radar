"""Regression tests: audited FedDev recipients and conditional western selection."""
from __future__ import annotations
import csv
import json
import tempfile
import unittest
from pathlib import Path

from gta_feddev_recipient_import import run as import_recipients, OUT, STATUS


class FedDevRecipientImportTests(unittest.TestCase):
    def test_all_78_are_historical_and_not_verified_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = import_recipients(tmp)
            self.assertEqual(result["rows"], 78)
            self.assertEqual(result["open_orders_verified"], 0)
            self.assertEqual(result["live_procurement_rechecks_performed"], 0)
            with (Path(tmp) / OUT).open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 78)
            self.assertEqual(len({(r["company"], r["city"], r["official_backgrounder_url"]) for r in rows}), 78)
            self.assertTrue(all(r["buyer_verified"] == "False" for r in rows))
            self.assertTrue(all(r["open_equipment_order_verified"] == "False" for r in rows))
            self.assertTrue(all(r["freshness"].startswith("HISTORICAL_") for r in rows))
            self.assertTrue(all(r["official_backgrounder_url"].startswith("https://") for r in rows))
            self.assertEqual(json.loads((Path(tmp)/STATUS).read_text())["rows"],78)

    def test_import_fails_closed_without_complete_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "partial.csv"
            source.write_text("Recipient / company,City,Official backgrounder URL\nA,B,https://example.com\n")
            with self.assertRaises(ValueError):
                import_recipients(tmp, source=source)

    def test_full_run_stage_order(self):
        from gta_monday_full_run import stages
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            names=[name for name,_,_ in stages(root, root/"GTA_RADAR_RESULTS")]
            self.assertLess(names.index("feddev_all40_evidence"),
                            names.index("feddev_recipient_evidence_import"))
            self.assertLess(names.index("feddev_recipient_evidence_import"),
                            names.index("equipment_commercial_index"))
            self.assertIn("industrial_fulltext_news",names)

    def test_31_scope_is_source_gated_and_not_automatically_published(self):
        from gta_western_31_city_combined import run as western_run
        # Contract: western reconciliation requires a validated 28-city
        # baseline and cannot populate paid candidates from a missing source.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises((ValueError, FileNotFoundError)):
                western_run(tmp)


if __name__ == "__main__":
    unittest.main()
