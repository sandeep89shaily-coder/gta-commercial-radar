"""Offline tests for Toronto AIC voluntary email importer and top research summary."""
import csv
import tempfile
import unittest
from pathlib import Path
import toronto_aic_email_import as aic
import early_pilot_summary as summary

EML=b"""From: City Updates <updates@toronto.ca>
To: citizen@example.org
Date: Sat, 24 Oct 2026 08:30:00 -0400
Subject: Ward development applications
MIME-Version: 1.0
Content-Type: text/html; charset="utf-8"

<html><body><p>New application link</p>
<a href="https://www.toronto.ca/city-government/planning-development/application-information-centre/?file=24OZ0123">Industrial warehouse expansion</a>
<a href="https://example.com/untrusted">Click here</a></body></html>
"""


class Tests(unittest.TestCase):
    def test_official_links_imported_without_claimed_publication(self):
        rows=aic.extract_message(EML)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["source_date"],"")
        self.assertEqual(rows[0]["procurement_status"],"UNKNOWN")
        self.assertEqual(rows[0]["commercial_fit"],"POSSIBLE_COMMERCIAL")
        self.assertEqual(rows[0]["attributes"]["email_header_date_not_publication"],
                         "2026-10-24")
        self.assertIn("UNAUTHENTICATED",rows[0]["verification"])

    def test_untrusted_sender_rejected(self):
        self.assertEqual(aic.extract_message(
          EML.replace(b"updates@toronto.ca",b"updates@fake.example.org")),[])

    def test_no_mail_is_not_fake_zero(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/"out"
            self.assertEqual(aic.run(str(Path(root)/"missing"),str(Path(root)/"db"),str(out)),0)
            with (out/"EARLY_AIC_EMAIL_STATUS.csv").open(encoding="utf-8-sig",newline="") as stream:
                status=list(csv.DictReader(stream))
            self.assertEqual(status[0]["status"],"NO_EMAIL_INPUT")

    def test_email_first_observation_baseline(self):
        with tempfile.TemporaryDirectory() as root:
            msgs=Path(root)/"mail";msgs.mkdir()
            (msgs/"notice.eml").write_bytes(EML)
            out=Path(root)/"result"
            self.assertEqual(aic.run(str(msgs),str(Path(root)/"data"),str(out)),0)
            with (out/"EARLY_AIC_EMAIL_RESEARCH.csv").open(encoding="utf-8-sig",newline="") as s:
                records=list(csv.DictReader(s))
            self.assertEqual(len(records),1)

    def test_summary_scores_public_date_but_never_qualifies(self):
        row=dict(source_id="pickering_proposals",item_id="new1",city="PICKERING",
                 site="123 Test Rd",title="New industrial warehouse",
                 record_url="https://www.pickering.ca/news/posts/test/",
                 official_public_posting_date="2026-10-22",
                 radar_first_seen="2026-10-24T11:00:00",
                 lead_status="NOT_SALE_READY_RESEARCH_ONLY",
                 matched_sources="",published_entity="Developer Corp")
        items=summary.preview_candidates([row],today=__import__("datetime").date(2026,10,24))
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["lead_status"],"NOT_SALE_READY_RESEARCH_ONLY")
        self.assertEqual(items[0]["why_research"],"OFFICIAL_PUBLIC_POST_WITHIN_180_DAYS")
        self.assertEqual(summary.preview_candidates([{**row,"lead_status":"VERIFIED"}],
                        today=__import__("datetime").date(2026,10,24)),[])


if __name__=="__main__":unittest.main()
