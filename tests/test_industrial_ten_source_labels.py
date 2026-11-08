"""Human-labeled ERO official-page scope QA; not a live-collector acceptance test."""
import json
import unittest
from pathlib import Path

from gta_industrial_equipment_pilot import TARGET_CITIES, equipment_changes
from gta_ero_notice_detail import CITY_ALIASES

FIXTURE = Path(__file__).resolve().parents[1] / (
    "research/ero_industrial_ten_official_source_scope_labels_20261108.json"
)

class EROTenPublicSourceLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))["samples"]

    def test_ten_distinct_original_official_notice_urls_and_no_sales_claims(self):
        self.assertEqual(len(self.data), 10)
        self.assertEqual(len({r["ero_number"] for r in self.data}), 10)
        for row in self.data:
            self.assertEqual(row["official_notice_url"],
                             "https://ero.ontario.ca/notice/" + row["ero_number"])
            self.assertFalse(row["verified_buyer"])
            self.assertFalse(row["verified_open_procurement"])

    def test_explicit_equipment_change_vs_scope_only_human_review(self):
        positives = []
        false_positives = []
        for row in self.data:
            found = equipment_changes(row["review_excerpt"])
            label = row["human_label"]
            if label == "EXPLICIT_PHYSICAL_CHANGE":
                matches = [
                    x for x in found if x["action"] == row["expected_action"]
                    and x["equipment"] == row["expected_equipment"]
                    and x["replacement_equipment"] ==
                        row["expected_replacement_equipment"]
                ]
                self.assertEqual(len(matches), 1,
                    "Missing explicitly sourced change on " + row["ero_number"])
                positives.append(row["ero_number"])
            elif found:
                false_positives.append((row["ero_number"], found))
        self.assertEqual(set(positives), {"026-1152", "026-1155"})
        self.assertEqual(false_positives, [],
            "Source scope/renewal cannot be auto-converted to new equipment orders")

    def test_source_verified_southern_ontario_municipalities_are_in_scope(self):
        self.assertIn("bradford west gwillimbury", TARGET_CITIES)
        self.assertIn("niagara-on-the-lake", TARGET_CITIES)
        self.assertEqual(CITY_ALIASES["town of bradford west gwillimbury"],
                         "Bradford West Gwillimbury")

    def test_physical_site_gate_rejects_mobile_and_outside_locations(self):
        by_id = {r["ero_number"]: r for r in self.data}
        for no in ("026-1151", "026-0989", "026-0955"):
            row = by_id[no]
            self.assertNotIn(row["city"].casefold(), TARGET_CITIES)

if __name__ == "__main__":
    unittest.main()
