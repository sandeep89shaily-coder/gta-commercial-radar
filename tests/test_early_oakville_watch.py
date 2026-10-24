"""Strict offline Oakville seven-ward and document tests (no network)."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
import early_oakville_watch as o

HOME="""<html><body><main><h1>Active Development Applications</h1>
"""+"".join(
    '<a href="/business-development/planning-development/active-development-applications/'
    f'ward-{i}-development-and-site-plan-applications/">'
    f'Ward {i} - Development and Site Plan Applications</a>'
    for i in range(1,8))+"</main></body></html>"

def ward_html(i):
    return f"""<html><body><main><h1>Ward {i}</h1>
<h2>Development Applications</h2>
<a href="/business-development/planning-development/active-development-applications/ward-{i}-development-and-site-plan-applications/example-development/">Development Ltd. - 100 Main Street - Z.1000.01</a>
<h2>Site Plan Applications</h2>
<a href="/business-development/planning-development/active-development-applications/ward-{i}-development-and-site-plan-applications/factory-renovation/">Cameron's Brewery - 1165 Invicta Drive - 1509.001/01</a>
<h2>Recently Approved Site Plan Applications</h2>
<a href="/business-development/planning-development/active-development-applications/ward-{i}-development-and-site-plan-applications/approved-project/">Industrial approved project - 199 Test Rd - 1509.002/01</a>
<h2>You might be interested in</h2>
<a href="/en/other/news">Unrelated navigation</a>
</main></body></html>"""

DETAIL="""<html><body><main><h1>Cameron's Brewery</h1>
<p>Site Plan Application</p><p>1165 Invicta Drive</p><p>File No: 1509.001/01</p>
<h2>Description</h2><p>A new industrial warehouse expansion including loading docks.</p>
<h2>Contact information</h2><p>planningapps@oakville.ca</p>
<h2>Supporting documents</h2><ul>
<li><a href="/downloads/a.pdf">Submission 1 - Site Plan - May 2026</a></li>
<li><a href="/downloads/b.pdf">Submission 2 - Elevation Plan - September 2026</a></li>
</ul></main></body></html>"""

class Response:
    def __init__(self,body):self.text=body
    def raise_for_status(self):pass

class Session:
    def __init__(self,items):self.items=items
    def get(self,url,**kwargs):
        if url not in self.items:raise o.requests.RequestException("fixture missing")
        return Response(self.items[url])

class Tests(unittest.TestCase):
    def fixture(self):
        urls=o.ward_urls(HOME)
        pages={o.BASE:HOME}
        for i,url in enumerate(urls,1):
            pages[url]=ward_html(i)
            for item in o.parse_ward(ward_html(i),url):
                pages[item["source_url"]]=DETAIL
        return pages

    def test_seven_ward_links_and_missing_ward(self):
        self.assertEqual(len(o.ward_urls(HOME)),7)
        with self.assertRaisesRegex(RuntimeError,"seven"):
            o.ward_urls(HOME.replace("Ward 7 - Development","Disabled ward"))

    def test_all_sections_and_safe_links(self):
        ward=o.ward_urls(HOME)[5]
        found=o.parse_ward(ward_html(6),ward)
        self.assertEqual(len(found),3)
        self.assertEqual(found[1]["stage"],"SITE_PLAN")
        self.assertEqual(found[1]["site"],"1165 Invicta Drive")
        self.assertEqual(found[1]["company"],"Cameron's Brewery")
        self.assertEqual(found[1]["commercial_fit"],"POSSIBLE_COMMERCIAL")
        self.assertEqual(found[1]["source_date"],"")
        self.assertEqual(found[1]["procurement_status"],"UNKNOWN")
        with self.assertRaises(ValueError):
            o.local_url(o.BASE,"https://private.example.com/file")

    def test_detail_dates_not_publication_and_no_buyer(self):
        ward=o.ward_urls(HOME)[5]
        record=o.parse_ward(ward_html(6),ward)[1]
        found=o.detail(DETAIL,record)
        self.assertIn("warehouse expansion",found["description"])
        self.assertEqual(found["file_number"],"1509.001/01")
        self.assertIn("May 2026",found["document_label_months_not_posting_dates"])
        self.assertEqual(found["procurement_status"],"UNKNOWN")
        self.assertIn("NOT_IDENTIFIED",found["purchasing_contact"])
        self.assertEqual(found["detail_classification"],"POSSIBLE_COMMERCIAL")

    def test_baseline_repeat_and_one_source_change(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)
            opts=dict(data_dir=f/"data",output_dir=f/"result",max_details=3)
            fixture=self.fixture()
            self.assertEqual(o.run(**opts,session=Session(fixture),
                                  observed="2026-10-24T16:00:00+00:00"),0)
            self.assertEqual(o.run(**opts,session=Session(fixture),
                                  observed="2026-10-25T16:00:00+00:00"),0)
            changed=dict(fixture)
            ward=o.ward_urls(HOME)[5]
            changed[ward]=changed[ward].replace("Cameron's Brewery", "Cameron's Brewing")
            self.assertEqual(o.run(**opts,session=Session(changed),
                                  observed="2026-10-26T16:00:00+00:00"),0)
            with (f/"result"/"EARLY_OAKVILLE_CHANGES_REVIEW_ONLY.csv").open(
                    encoding="utf-8-sig",newline="") as stream:
                events=list(csv.DictReader(stream))
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]["change_type"],"UPDATED")
            db=sqlite3.connect(f/"data"/"early_oakville_review.sqlite")
            self.assertEqual(db.execute("SELECT count(*) FROM changes").fetchone()[0],1)
            db.close()

    def test_failure_retains_history(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)
            opts=dict(data_dir=f/"data",output_dir=f/"results",max_details=0)
            self.assertEqual(o.run(**opts,session=Session(self.fixture()),
                                   observed="2026-10-24T10:00:00+00:00"),0)
            self.assertEqual(o.run(**opts,session=Session({}),
                                   observed="2026-10-25T10:00:00+00:00"),1)
            db=sqlite3.connect(f/"data"/"early_oakville_review.sqlite")
            self.assertEqual(db.execute("SELECT count(*) FROM snapshots").fetchone()[0],21)
            db.close()

if __name__=="__main__":
    unittest.main()
