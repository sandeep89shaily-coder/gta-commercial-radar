"""Burlington publisher 403 and Brampton eSCRIBE JS-shell fallbacks."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
import early_discovery_watch as discovery

HOME="""<html><body><nav><div>Current Development Projects
<a href="/en/news/current-development-projects/ward1.aspx">Ward 1</a>
<a href="/en/news/current-development-projects/ward2.aspx">Ward 2</a>
<a href="/en/news/current-development-projects/ward3.aspx">Ward 3</a>
</div></nav></body></html>"""
WARD="""<html><body><h1>Current Development Projects Ward 1</h1>
<a href="/en/news/current-development-projects/open-industrial.aspx">Industrial</a>
<a href="/en/news/current-development-projects/blocked-development.aspx">Blocked</a>
</body></html>"""
PROJECT="""<html><body><h1>Industrial site expansion</h1>
<p>Status - Pre-Application</p><h2>Ward 4 Site Address</h2><p>100 Test Rd</p>
<h3>Applicant</h3><p>Industrial Holdings Ltd.</p>
<h3>Proposed Development</h3><p>Industrial warehouse with loading docks.</p>
<h3>Public Meetings</h3></body></html>"""
MID="25022e86-016b-490b-b051-1bae3971fa77"
CAL=f"""<html><body><div class="meeting-row">
<h3 class="meeting-title-heading"><span aria-label="Planning and Development Committee Monday, November 02, 2026 @ 7:00 PM">Planning and Development Committee</span></h3>
<a href="/Meeting.aspx?Id={MID}&amp;lang=English">View agenda</a>
</div></body></html>"""

class R:
    def __init__(self,text):self.text=text
    def raise_for_status(self):pass
class S:
    def __init__(self,items):self.items=items
    def get(self,url,**kw):
        if url not in self.items:raise discovery.requests.RequestException("403 denied")
        return R(self.items[url])

class Test(unittest.TestCase):
    def test_burlington_must_not_commit_403_as_new_or_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            wards=discovery.discover_burlington_ward_urls(HOME)
            m={discovery.BURLINGTON_HOME:HOME,**{w:WARD for w in wards}}
            m["https://www.burlington.ca/en/news/current-development-projects/open-industrial.aspx"]=PROJECT
            opts=dict(data_dir=root/"data",out_dir=root/"out",
                 source=["burlington_ward_discovery"])
            self.assertEqual(discovery.run(**opts,session=S(m),now="2026-10-24T10:00:00Z"),0)
            statuses=list(csv.DictReader((root/"out"/"EARLY_DISCOVERY_SOURCE_STATUS.csv").open(encoding="utf-8-sig")))
            self.assertEqual(statuses[0]["status"],"PARTIAL_UNCOMMITTED")
            self.assertEqual(statuses[0]["fetched"],"1")
            self.assertTrue((root/"out"/"EARLY_BURLINGTON_PARTIAL_REVIEW.csv").is_file())
            db=sqlite3.connect(root/"data"/"early_discovery_review.sqlite")
            self.assertEqual(db.execute("SELECT count(*) FROM snapshots").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT count(*) FROM changes").fetchone()[0],0)
            db.close()
            blocked=list(csv.DictReader((root/"out"/"EARLY_BURLINGTON_BLOCKED_DETAILS.csv").open(encoding="utf-8-sig")))
            self.assertEqual(len(blocked),1)

    def test_brampton_calendar_works_even_if_js_agenda_empty(self):
        dates=discovery._brampton_calendar_dates(CAL)
        self.assertEqual(dates[MID],"2026-11-02")
        url=next(iter(discovery.parse_calendar(CAL).values()))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            opts=dict(data_dir=root/"data",out_dir=root/"out",
                      source=["brampton_planning_agendas"])
            self.assertEqual(discovery.run(**opts,session=S({
                discovery.BRAMPTON_CALENDAR:CAL,
                url:"<html><body>Powered by eSCRIBE Software Ltd.</body></html>"}),
                now="2026-10-24T10:00:00Z"),0)
            status=list(csv.DictReader((root/"out"/"EARLY_DISCOVERY_SOURCE_STATUS.csv").open(encoding="utf-8-sig")))[0]
            self.assertEqual(status["status"],"PARTIAL_CALENDAR_ONLY")
            db=sqlite3.connect(root/"data"/"early_discovery_review.sqlite")
            row=db.execute("SELECT content FROM snapshots").fetchone()[0]
            self.assertIn("2026-11-02",row)
            self.assertIn("CALENDAR_ONLY",row)
            self.assertNotIn("POSSIBLE_COMMERCIAL",row)
            db.close()

if __name__=="__main__":
    unittest.main()
