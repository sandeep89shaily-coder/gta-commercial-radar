"""Offline acceptance for the daily equipment opportunity index."""
import csv
import tempfile
import unittest
from pathlib import Path

from gta_equipment_commercial_daily import run, OUTPUT

def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

class EquipmentCommercialIndexTests(unittest.TestCase):
    def test_combines_ero_and_cited_investment_without_buyers_or_spend(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root / "INDUSTRIAL_PILOT" /
                  "GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv", [{
                "ero_number": "019-1234", "official_notice_url":
                "https://ero.ontario.ca/notice/019-1234",
                "proponent": "Example Process Inc", "site_address": "10 Example Rd",
                "city": "Toronto", "equipment": "Dust collection",
                "action": "INSTALLATION", "proposal_posted": "2026-11-16",
            }])
            write(root / "GTA_RADAR_INVESTMENT_CONTACT_BRIDGE" /
                  "GTA_RADAR_EQUIPMENT_INVESTMENT_OPPORTUNITIES.csv", [{
                "company_source_claim": "Example Equipment Ltd",
                "project_address_source_claim": "24 Plant Rd",
                "city": "Brampton",
                "equipment_or_investment_scope_quote": "New production line",
                "source_urls": "https://example.org/company-announcement",
            }])
            report = run(root)
            self.assertEqual(report["candidate_count"], 2)
            self.assertEqual(report["sources"], {"ero": 1, "investment": 1})
            self.assertTrue(report["no_network_or_paid_calls"])
            with (root / OUTPUT).open(encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(all(r["purchasing_authority_verified"] == "False"
                                and r["open_supplier_package_verified"] == "False"
                                and r["contact_email_verified"] == ""
                                for r in rows))
            self.assertNotEqual(rows[0]["source_date_basis"],
                                "VERIFIED_FIRST_PUBLICATION")
            self.assertFalse((root / "v5_ai_budget.sqlite").exists())

    def test_absent_inputs_yield_header_only_not_imaginary_prospects(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = run(root)
            self.assertEqual(report["candidate_count"], 0)
            self.assertTrue((root / OUTPUT).exists())

if __name__ == "__main__":
    unittest.main()
