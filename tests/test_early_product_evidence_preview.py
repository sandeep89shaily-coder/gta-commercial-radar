"""Evidence sample is not sales collateral; links and HTML escaped."""
import json
import tempfile
import unittest
from pathlib import Path
import early_product_evidence_preview as p

class Tests(unittest.TestCase):
    def test_current_research_sources_and_no_phantom_purchasing(self):
        cases=p.read_cases(
          "research/hamilton_public_business_evidence_20261024.json",
          "research/hamilton_formal_consultation_followups_20261024.json",
          "research/markham_2026_10_circulation_review.json")
        self.assertEqual(len(cases),22)  # 12 Hamilton companies + 7 consultation + 3 Markham
        self.assertTrue(all(x["lead_status"]!="VERIFIED_SALE_READY" for x in cases))
        self.assertTrue(any(x["location"]=="1133 Industrial Drive, Hamilton" for x in cases))
        text=p.render(cases)
        self.assertIn("NOT A VERIFIED OPEN CONTRACT",text)
        self.assertIn("Circulation date",text) if "Circulation date" in text else self.assertIn(
          "CIRCULATION_DATE_NOT_FIRST_PUBLIC_POSTED",text)

    def test_html_escapes_untrusted_public_page_titles(self):
        cases=[dict(key="test",region="MARKHAM",location="<img src=x onerror=alert(1)>",
          project="<script>alert(1)</script>",scope="<danger>",
          published_role="UNVERIFIED",source_type="PLANNING",source_date="UNKNOWN",
          date_basis="UNKNOWN",sources=["https://www.markham.ca/test?q=x&y=1",
          "javascript:alert(1)"],contact_channel="",contact_status="",
          procurement_status="UNKNOWN",vendor_state="UNKNOWN",buyer_state="UNVERIFIED",
          next_step="Verify",lead_status="NOT_SALE_READY_RESEARCH_ONLY")]
        page=p.render(cases)
        self.assertNotIn("<script>alert(1)</script>",page)
        self.assertNotIn("<img src=x onerror=alert(1)>",page)
        self.assertNotIn('href="javascript:',page)
        self.assertIn("&lt;danger&gt;",page)

    def test_offline_outputs_never_show_sale_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(p.run(folder),0)
            out=Path(folder)
            html=(out/"GTA_RADAR_INTERNAL_EVIDENCE_DOSSIERS.html").read_text(encoding="utf-8")
            metrics=json.loads((out/"GTA_RADAR_INTERNAL_QUALIFICATION_SCORECARD.json").read_text())
            self.assertIn("internal prototype",html)
            self.assertEqual(metrics["research_cases"],22)
            self.assertEqual(metrics["verified_open_private_work_packages"],0)
            self.assertFalse(metrics["external_distribution_approved"])

if __name__=="__main__":unittest.main()
