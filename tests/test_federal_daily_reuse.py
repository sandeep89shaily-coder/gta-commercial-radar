"""Retained federal research must survive daily run without the original grants.csv."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from gta_equipment_commercial_daily import run
from gta_federal_industrial_funding import OUTPUT as FEDERAL_CANDIDATES

class FederalDailyReuseTests(unittest.TestCase):
    def test_reuses_previous_snapshot_without_raw_2gb_csv(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            candidate={
                "funding_record_id":"F-2026-1",
                "recipient":"Example CNC Manufacturing Inc",
                "recipient_city":"Toronto",
                "recipient_province":"Ontario",
                "funding_value_cad_as_published":"2500000",
                "agreement_title":"New equipment investment",
                "activity_excerpt":"Acquire CNC bending equipment and automate manufacturing production lines.",
                "date_as_published":"2026-05-01",
                "date_type":"FUNDING_AGREEMENT",
                "capital_signal":"CAPEX",
                "source_dataset":"https://open.canada.ca/data/en/dataset/432527ab-7aac-45b5-81d6-7597107a7013",
            }
            path=root/FEDERAL_CANDIDATES
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(candidate));writer.writeheader();writer.writerow(candidate)
            before=path.read_bytes()
            summary=run(root)
            self.assertEqual(summary["federal_industrial_funding"]["status"],
                             "REUSED_SAVED_OFFICIAL_FUNDING_CANDIDATES")
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(summary["federal_capex_qualification"]["qualified_records"],1)
            self.assertTrue((root/"GTA_RADAR_FEDERAL_CAPEX_TOP20_RESEARCH.csv").exists())

    def test_no_snapshots_fail_closed_without_invented_data(self):
        with tempfile.TemporaryDirectory() as d:
            summary=run(d)
            self.assertEqual(summary["federal_industrial_funding"]["status"],
                             "NO_LOCAL_OFFICIAL_SNAPSHOT")
            self.assertEqual(summary["federal_capex_qualification"]["qualified_records"],0)

if __name__=="__main__":
    unittest.main()
