"""Brampton first-party Planning and Development featured cards: offline gates."""
import json
import tempfile
import unittest
from pathlib import Path

from gta_brampton_featured_pdc import parse, run, LEDGER, CSV, STATUS, SOURCE

MARKUP = """
<h2>Featured Application: June 8, 2026</h2>
<p>An application made by Humberwest Parkway RDP 1724 Inc. – Weston Consulting
(City File: OZS-2025-0038) Ward 8 to Amend the Official Plan</p>
<h3>Location</h3><p>West side of Humberwest Parkway, north of Williams Parkway.
No municipal address (0 Edvac Drive)</p>
<h3>Purpose</h3><p>The purpose of the application is to amend the Official Plan
and Zoning By-law to permit development of 41 three-storey townhouse units.</p>
<h2>Featured Application: June 15, 2026</h2>
<p>An application made by Upper Mayfield Estates / Caliber Homes -
KLM Planning Partners Inc. (City File:OZS-2025-0048) Ward 10</p>
<h3>Location</h3><p>5875 Mayfield Road</p>
<h3>Purpose</h3><p>The purpose is to permit an office mixed-use block,
with ground-floor offices and residential units.</p>
<h3>About the PDC:</h3><p>General public information.</p>
"""

class BramptonFeaturedTests(unittest.TestCase):
    def test_extracts_two_exact_city_file_numbers_and_no_false_procurement(self):
        cards, holds, seen = parse(MARKUP)
        self.assertTrue(seen)
        self.assertEqual(len(cards), 2)
        self.assertEqual(holds, 0)
        self.assertEqual([c["application_id"] for c in cards],
                         ["OZS-2025-0038", "OZS-2025-0048"])
        self.assertEqual(cards[1]["location_text"], "5875 Mayfield Road")
        self.assertIn("mixed-use", cards[1]["purpose_text"])
        self.assertFalse(cards[0]["project_verified"])
        self.assertFalse(cards[0]["original_publication_date_verified"])
        self.assertFalse(cards[1]["open_procurement_verified"])

    def test_repeated_source_content_is_not_new_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = run(root, markup=MARKUP)
            again = run(root, markup=MARKUP)
            self.assertEqual(first["newly_observed_cards_not_new_publications"], 2)
            self.assertEqual(again["newly_observed_cards_not_new_publications"], 0)
            self.assertEqual(again["changed_cards_not_new_projects"], 0)
            self.assertEqual(json.loads((root/LEDGER).read_text())["version"], 1)
            self.assertTrue((root/CSV).is_file())

    def test_unrecognizable_page_does_not_erase_existing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, markup=MARKUP)
            saved = (root/LEDGER).read_bytes()
            result = run(root, markup="<html>Nothing published here</html>")
            self.assertEqual(result["status"], "SOURCE_STRUCTURE_UNVERIFIED_OR_EMPTY_HOLD")
            self.assertEqual((root/LEDGER).read_bytes(), saved)

    def test_no_network_without_explicit_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(Path(tmp))
            self.assertEqual(result["status"], "DRY_RUN_EXPLICIT_FETCH_REQUIRED")
            self.assertEqual(result["paid_ai_calls"], 0)
            self.assertFalse((Path(tmp)/LEDGER).exists())

    def test_no_publication_date_inferred_from_meeting_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(tmp, markup=MARKUP)
            self.assertEqual(result["first_publications_verified"], 0)
            self.assertEqual(result["verified_buyers"], 0)
            self.assertEqual(result["commercial_keyword_cards_review_only"], 1)

if __name__ == "__main__":
    unittest.main()
