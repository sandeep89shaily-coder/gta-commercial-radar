"""Toronto schedule->TMMIS only promotes same-date committee/meeting item lists."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_toronto_schedule_tmmis_bridge import (
    parse, run, select, agenda_items_url, LEDGER, OUTPUT, STATUS
)

HTML = """
<html><body>
<h2>Planning and Housing Committee- Meeting 31</h2>
<p>Meeting Date and Status: Thursday, June 11, 2026 - 9:30 AM - Complete</p>
<ul><li><a href="/council/agenda-item.do?item=2026.PH31.1">PH31.1</a>
<span>9:30 AM</span><h5>Our Plan Toronto: East Harbour Employment Area Conversion</h5></li>
<li><a href="/council/agenda-item.do?item=2026.PH31.2">PH31.2</a>
<h5>Zoning for Low-Carbon Technologies - Final Report</h5></li>
<li><span>PH31.4</span>
<h5>Toronto Builds: 40 Bushby Drive - Official Plan Amendment Approval</h5></li></ul>
</body></html>
"""

def schedule(root):
    root = Path(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    with root.open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f, fieldnames=[
            "meeting_date","committee","meeting_number","start_time","location",
            "term","schedule_evidence","agenda_url","agenda_retrieved",
            "publication_date_verified","project_verified"])
        w.writeheader()
        w.writerow({
            "meeting_date":"2026-06-11",
            "committee":"Planning and Housing Committee",
            "meeting_number":"31",
            "term":"2022-2026",
            "schedule_evidence":"CITY_CLERK_PUBLISHED_SCHEDULE_ONLY"})
        w.writerow({
            "meeting_date":"2026-06-11",
            "committee":"Audit Committee",
            "meeting_number":"31",
            "term":"2022-2026",
            "schedule_evidence":"CITY_CLERK_PUBLISHED_SCHEDULE_ONLY"})
    return root

class TorontoScheduleAgendaBridgeTests(unittest.TestCase):
    def test_verifies_exact_meeting_number_date_and_actual_titles(self):
        parsed = parse(HTML, meeting_date="2026-06-11", meeting_number=31)
        self.assertEqual(len(parsed),3)
        self.assertEqual(parsed[0]["item_code"],"PH31.1")
        self.assertIn("40 Bushby Drive", parsed[-1]["item_title"])
        with self.assertRaisesRegex(ValueError,"DATE_MISMATCH"):
            parse(HTML,meeting_date="2026-06-12",meeting_number=31)
        with self.assertRaisesRegex(ValueError,"TITLE_NUMBER_MISMATCH"):
            parse(HTML,meeting_date="2026-06-11",meeting_number=32)

    def test_requires_official_schedule_identity_and_no_background_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=schedule(Path(tmp)/"source.csv")
            rows=select(f)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["candidate_url"],agenda_items_url(2026,31))
            self.assertFalse(any("audit" in x["candidate_url"] for x in rows))

    def test_never_claims_publisher_first_date_or_business_buyer(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=schedule(Path(tmp)/"source.csv")
            url=agenda_items_url(2026,31)
            calls=[]
            def fake(url_requested):
                calls.append(url_requested)
                self.assertEqual(url_requested,url)
                return HTML
            r=run(f, Path(tmp)/"review",
                  source_status="RECENT_SCHEDULE_REVIEW_ONLY",
                  fetch=True, fetcher=fake,
                  now=dt.datetime(2026,11,13,tzinfo=dt.timezone.utc))
            self.assertEqual(calls,[url])
            self.assertEqual(r["status"],"OFFICIAL_ITEM_LIST_REVIEW_ONLY")
            self.assertEqual(r["original_tmmis_items_extracted"],3)
            self.assertEqual(r["verified_project_count"],0)
            self.assertEqual(r["buyer_verified"],0)
            self.assertEqual(r["first_publisher_publication_dates_verified"],0)
            self.assertEqual(r["paid_ai_calls"],0)
            with (Path(tmp)/"review"/OUTPUT).open(encoding="utf-8-sig") as inp:
                rows=list(csv.DictReader(inp))
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[0]["change_event"],"FIRST_OBSERVED_ITEM_NOT_FIRST_PUBLISHED")
            r2=run(f, Path(tmp)/"review",
                   source_status="RECENT_SCHEDULE_REVIEW_ONLY",
                   fetch=True, fetcher=fake,
                   now=dt.datetime(2026,11,14,tzinfo=dt.timezone.utc))
            self.assertEqual(r2["status"],"OFFICIAL_ITEM_LIST_REVIEW_ONLY")
            with (Path(tmp)/"review"/OUTPUT).open(encoding="utf-8-sig") as inp:
                rows2=list(csv.DictReader(inp))
            self.assertTrue(all(r["change_event"]=="UNCHANGED" for r in rows2))
            self.assertEqual(rows2[0]["first_observed_utc"],rows[0]["first_observed_utc"])

    def test_blocked_or_wrong_date_keeps_original_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=schedule(Path(tmp)/"source.csv")
            out=Path(tmp)/"review"
            run(f,out,source_status="RECENT_SCHEDULE_REVIEW_ONLY",
                fetch=True,fetcher=lambda _:HTML)
            previous=(out/LEDGER).read_bytes()
            bad=run(f,out,source_status="RECENT_SCHEDULE_REVIEW_ONLY",
                    fetch=True,fetcher=lambda _:HTML.replace(
                        "Thursday, June 11","Friday, June 12"))
            self.assertEqual(bad["status"],"NO_OFFICIAL_TMMIS_MEETING_CONTENT_VERIFIED")
            self.assertEqual((out/LEDGER).read_bytes(),previous)
            self.assertTrue((out/STATUS).is_file())

    def test_stale_schedule_never_generates_http_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=schedule(Path(tmp)/"source.csv")
            called=[]
            r=run(f, Path(tmp)/"review", source_status="OFFICIAL_SCHEDULE_BLOCKED_OR_SCHEMA_HELD",
                  fetch=True,fetcher=lambda _:called.append(True))
            self.assertEqual(called,[])
            self.assertEqual(r["status"],"CURRENT_OFFICIAL_SCHEDULE_NOT_VALIDATED_HOLD")

if __name__=="__main__":
    unittest.main()
