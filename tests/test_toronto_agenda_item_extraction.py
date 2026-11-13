"""Toronto TMMIS item extraction must remain evidence-only and fully offline."""
import json
import tempfile
import unittest
from pathlib import Path

from gta_toronto_agenda_item_extraction import parse, build, CSV, JSON

URL="https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda"
PDF1="https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-287888.pdf"
PDF2="https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287889.pdf"


class TorontoAgendaItemTests(unittest.TestCase):
    def test_item_boundary_and_attachment_attribution(self):
        markup = (
            '<h2>Planning and Housing</h2>'
            '<h3><span>PH30.1 - Proposed Industrial Development at 10 Test Road</span></h3>'
            '<p>Background information</p>'
            '<a href="'+PDF1+'">Staff report</a>'
            '<a href="https://evil.example/legdocs/mmis/2026/ph/bgrd/backgroundfile-99.pdf">Bad link</a>'
            '<h3>CC41.2 - Confirmation of Minutes</h3>'
            '<a href="'+PDF2+'">Minutes</a>'
        )
        result=parse(markup,URL)
        self.assertEqual([i["item_code"] for i in result],["PH30.1","CC41.2"])
        self.assertEqual(result[0]["attachment_urls"],[PDF1])
        self.assertEqual(result[1]["attachment_urls"],[PDF2])
        self.assertEqual(result[0]["screening"],"RESEARCH_CANDIDATE_TITLE_ONLY")
        self.assertEqual(result[1]["screening"],"OTHER_AGENDA_ITEM")
        self.assertFalse(result[0]["buyer_verified"])
        self.assertFalse(result[0]["project_identity_verified"])

    def test_no_fabricated_publication_or_project_from_html(self):
        result=parse('<h3>PH30.5 - New Warehouse Expansion</h3>',URL)
        self.assertEqual(result[0]["screening"],"RESEARCH_CANDIDATE_TITLE_ONLY")
        self.assertIsNone(result[0]["original_publication_date"])
        self.assertFalse(result[0]["procurement_verified"])
        self.assertEqual(result[0]["attachment_count"],0)

    def test_duplicate_code_and_non_tmmis_sources_rejected(self):
        with self.assertRaises(ValueError):
            parse('<h3>PH30.1 - Proposed industrial warehouse building</h3>'
                  '<h3>PH30.1 - Proposed industrial warehouse revised</h3>',URL)
        with self.assertRaises(ValueError):
            parse('<h3>PH30.1 - Proposed industrial warehouse building</h3>',
                  'https://example.com/council/report.do?meeting=2026.CC41&type=agenda')

    def test_json_csv_with_no_ai_or_downloads(self):
        markup='<h3>PH30.2 - Proposed Industrial Redevelopment</h3><a href="'+PDF1+'">Report</a>'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/"saved.html"
            path.write_text(markup,encoding="utf-8")
            result=build(path,URL,root/"out")
            self.assertEqual(result["item_count"],1)
            self.assertEqual(result["attachments_listed_not_downloaded"],1)
            self.assertEqual(result["verified_projects"],0)
            self.assertEqual(result["paid_ai_cost_usd"],0)
            self.assertTrue((root/"out"/CSV).is_file())
            evidence=json.loads((root/"out"/JSON).read_text(encoding="utf-8"))
            self.assertEqual(evidence["items"][0]["attachment_urls"],[PDF1])
            self.assertEqual(evidence["publication_dates_verified"],0)


if __name__ == "__main__":
    unittest.main()
