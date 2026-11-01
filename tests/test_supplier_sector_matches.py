"""Offline tests for broad supplier-sector classification and manual handoff."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from gta_supplier_scope import classify, TIERS
import gta_manual_project_list as listing


class SupplierSectorTests(unittest.TestCase):
    def test_all_ten_reviewed_project_scopes_have_relevant_sector(self):
        examples = [
            ("New industrial facility", "General contractors / construction management"),
            ("3-floor rear office addition to heritage building", "Heritage restoration / masonry contractors"),
            ("Industrial storage / fabric-covered steel building", "Fabric-covered industrial building suppliers"),
            ("Industrial roof, interior modifications and ground-floor addition", "Industrial roofing / building envelope"),
            ("Warehouse floor replacement and new loading doors", "Industrial flooring / concrete floor contractors"),
            ("321 kW DC rooftop commercial solar PV", "Commercial solar PV installers / EPC"),
            ("Commercial gym rooftop/second-floor addition", "Commercial gym equipment / sport flooring"),
            ("Auto-shop spray booth; separate mezzanine demolition", "Automotive paint booth manufacturers / installers"),
            ("Office/warehouse interior fit-out, HVAC and plumbing", "Commercial HVAC / mechanical contractors"),
            ("Industrial plant two-phase expansion, loading bays, cold storage", "Industrial refrigeration contractors"),
        ]
        for description, expected in examples:
            with self.subTest(scope=description):
                categories = {m["supplier_category"] for m in classify(description)}
                self.assertIn(expected, categories)

    def test_solar_rooftop_is_not_claimed_as_roof_replacement(self):
        matches = classify("321 kW rooftop solar PV installation")
        direct = {m["supplier_category"] for m in matches if m["match_tier"] == "SCOPE_LINKED"}
        self.assertIn("Commercial solar PV installers / EPC", direct)
        self.assertNotIn("Industrial roofing / building envelope", direct)

    def test_no_generic_matches_for_missing_scope(self):
        self.assertEqual(classify(""), [])
        self.assertEqual(classify("Permit application submitted"), [])

    def test_deduplicated_sector_and_unverified_no_award_claims(self):
        matches = classify("Solar installation and photovoltaic PV arrays on industrial warehouse")
        self.assertEqual(len({m["supplier_category"] for m in matches}), len(matches))
        self.assertEqual([TIERS.index(m["match_tier"]) for m in matches],
                         sorted(TIERS.index(m["match_tier"]) for m in matches))
        self.assertTrue(all(m["qualification"] == "SUGGESTION_ONLY_NO_AWARD_OR_BUYER_VERIFIED"
                            for m in matches))
        self.assertTrue(all(m["scope_phrase"] for m in matches))

    def test_manual_export_adds_filterable_sector_rows_without_buyer_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with (root/listing.SOURCE).open("w",newline="",encoding="utf-8-sig") as f:
                w=csv.DictWriter(f,fieldnames=["project_id","observation","description",
                                               "address","city","record_source_url"])
                w.writeheader()
                w.writerow({"project_id":"permit:1","observation":"FIRST_OBSERVED",
                            "description":"Warehouse floor replacement and new loading doors",
                            "address":"1 City View Dr","city":"Toronto",
                            "record_source_url":"https://www.toronto.ca/example"})
                w.writerow({"project_id":"permit:2","observation":"RECORD_CHANGED",
                            "description":"Permit application submitted",
                            "address":"2 Unknown St","city":"Toronto",
                            "record_source_url":"https://www.toronto.ca/other"})
            report=listing.build(root,today=dt.date(2026,11,1))
            self.assertEqual(report["verified_buyers_claimed"],0)
            self.assertEqual(report["supplier_packages_claimed"],0)
            with Path(report["supplier_matches_csv"]).open(encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f))
            self.assertGreater(len(rows),0)
            self.assertTrue(all(row["project_id"]=="permit:1" for row in rows))
            self.assertTrue(all(row["source_url"]=="https://www.toronto.ca/example" for row in rows))
            with Path(report["manual_review_csv"]).open(encoding="utf-8-sig",newline="") as f:
                manual=list(csv.DictReader(f))
            self.assertIn("Industrial flooring",manual[0]["supplier_scope_linked"])
            self.assertEqual(manual[1]["supplier_match_status"],"INSUFFICIENT_SCOPE")
            self.assertEqual(manual[0]["manual_notes"],"")
            page=Path(report["manual_review_html"]).read_text(encoding="utf-8")
            self.assertIn("supplier-sector matches",page)
            self.assertIn("NOT confirmed bid packages",page)


if __name__=="__main__":
    unittest.main()
