"""Offline deterministic tests: never contact municipalities/IESO or V8."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

import early_cue_watch as cue

IESO_HTML = """<!DOCTYPE html><html><body>
<h1>Application Status</h1><p>Last Updated: October 7, 2026</p>
<table><thead><tr><th>CAA ID &amp; Date</th><th>Queue</th>
<th>Applicant</th><th>Name</th><th>Transmission Zone</th><th>Type</th>
<th>Size</th><th>Proposed In-Service Date</th><th>SIA Status &amp; Report Links</th><th>Committed</th></tr></thead>
<tbody><tr><td>2026-EX1315</td><td></td><td>HYDRO ONE NETWORKS INC</td>
<td>E8V Thermal Upgrade</td><td>Essa</td><td>Equipment upgrade</td>
<td>-</td><td>2029-Q4</td><td>Complete</td><td>Yes</td></tr>
<tr><td>2026-914</td><td></td><td>BURLINGTON HYDRO INC.</td>
<td>Cumberland TS - Load Increase</td><td>Southwest</td><td>Increase load</td>
<td>20 MW</td><td>2028-Q2</td><td>Active</td><td></td></tr>
</tbody></table>
<p>1-7 of 2,085</p></body></html>"""

BURLINGTON_HTML = """<!DOCTYPE html><html><body>
<h1>3056376 Canada Inc. - 777 Guelph Line</h1><div>Status - Pre-Application</div>
<h2>Ward 4 Site Address</h2><div>777 Guelph Line</div>
<h2>Applicant</h2><p>3056376 Canada Inc.</p>
<h2>Proposed Development</h2><p>A mixed-use project including new retail,
office and commercial floor area, 3476 residential units.</p>
<h2>Public Meetings</h2><div>Pre-Application Community Meeting</div>
<div>April 22</div></body></html>"""

IESO_JSON_DATA=[
    dict(CaaId=i,CaaIdAndDate=f"2026-EX{i}",
         Name=f"Test project {i}",Applicant="Public Hydro Applicant",
         Location="Southwest",Type="Connection assessment",
         Size="20 MW",ProposedInServiceDate="2027-Q4<br>",
         SiaStatus="Active",Queue="",Committed="")
    for i in range(100,160)
]
IESO_JSON_DATA[1]["CaaIdAndDate"]="2026-914"
IESO_JSON_DATA[1]["Applicant"]="BURLINGTON HYDRO INC."

class FakeResponse:
    def __init__(self, value):
        self.text=value if isinstance(value,str) else ""
        self.value=value
    def raise_for_status(self):pass
    def json(self):return self.value

class Session:
    def __init__(self, mapping):
        self.mapping=mapping
        self.seen=[]
    def get(self,url,headers=None,timeout=None):
        self.seen.append(url)
        if url not in self.mapping:
            raise cue.requests.RequestException("offline fixture not supplied")
        return FakeResponse(self.mapping[url])

class CueTests(unittest.TestCase):
    def test_ieso_extracts_identifiers_and_partial_scope(self):
        items,warning=cue.parse_ieso(IESO_HTML)
        self.assertEqual(len(items),2)
        self.assertEqual(items[1]["record_id"],"2026-914")
        self.assertEqual(items[1]["company"],"BURLINGTON HYDRO INC.")
        self.assertEqual(items[1]["source_date"],"")
        self.assertEqual(items[1]["procurement_status"],"UNKNOWN")
        self.assertEqual(warning,"PAGINATED_WINDOW_NOT_FULL_QUEUE")
        self.assertEqual(items[1]["attributes"]["size"],"20 MW")

    def test_no_table_or_wrong_table_fails_no_fake_zero(self):
        for body in ("<html><body>No table</body></html>",
                     "<html><table><tr><th>Foo</th></tr><tr><td>bar</td></tr></table></html>"):
            with self.assertRaises(RuntimeError):
                cue.parse_ieso(body)

    def test_burlington_preapplication_not_publication_date(self):
        url=cue.BURLINGTON_PROJECT_URLS[0]
        row=cue.parse_burlington(BURLINGTON_HTML,url)
        self.assertEqual(row["stage"],"Pre-Application")
        self.assertEqual(row["company"],"3056376 Canada Inc.")
        self.assertEqual(row["source_date"],"")
        self.assertEqual(row["commercial_fit"],"REVIEW")
        self.assertEqual(row["signal_type"],"PRE_APPLICATION_MENTIONED")
        self.assertEqual(row["procurement_status"],"UNKNOWN")

    def test_baseline_repeats_and_actual_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            s=Session({cue.IESO_JSON:IESO_JSON_DATA})
            argv=dict(data_dir=root/"data",output_dir=root/"output",
                      sources=["ieso_connections"])
            self.assertEqual(cue.run(**argv,session=s,
                 observed="2026-10-24T09:00:00+00:00"),0)
            self.assertEqual(cue.run(**argv,session=s,
                 observed="2026-10-25T09:00:00+00:00"),0)
            # Preserve first seen and emit UPDATE only for true data edits.
            modified=[dict(x) for x in IESO_JSON_DATA]
            modified[1]["Size"]="30 MW"
            self.assertEqual(cue.run(**argv,session=Session({cue.IESO_JSON:modified}),
                 observed="2026-10-26T09:00:00+00:00"),0)
            with (root/"output"/"EARLY_CUES_CHANGES_REVIEW_ONLY.csv").open(
                        encoding="utf-8-sig",newline="") as stream:
                events=list(csv.DictReader(stream))
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]["change_type"],"UPDATED")
            self.assertEqual(events[0]["record_id"],"2026-914")
            self.assertEqual(events[0]["first_seen_at"],"2026-10-24T09:00:00+00:00")
            conn=sqlite3.connect(root/"data"/"early_cues_review.sqlite")
            self.assertEqual(conn.execute("select count(*) from changes").fetchone()[0],1)
            conn.close()

    def test_new_project_after_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            opts=dict(data_dir=Path(d)/"data",output_dir=Path(d)/"output",
                      sources=["ieso_connections"])
            cue.run(**opts,session=Session({cue.IESO_JSON:IESO_JSON_DATA}),
                    observed="2026-10-24T09:00:00+00:00")
            added=[dict(x) for x in IESO_JSON_DATA]
            added.append(dict(IESO_JSON_DATA[0],CaaId=933,
                CaaIdAndDate="2026-933",Name="Large Industrial Plant"))
            cue.run(**opts,session=Session({cue.IESO_JSON:added}),
                    observed="2026-10-25T09:00:00+00:00")
            with (Path(d)/"output"/"EARLY_CUES_CHANGES_REVIEW_ONLY.csv").open(
                    encoding="utf-8-sig",newline="") as stream:
                events=list(csv.DictReader(stream))
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]["record_id"],"2026-933")
            self.assertEqual(events[0]["change_type"],"NEW")
            self.assertEqual(events[0]["procurement_status"],"UNKNOWN")

    def test_failed_page_cannot_clear_history(self):
        with tempfile.TemporaryDirectory() as d:
            opts=dict(data_dir=Path(d)/"data",output_dir=Path(d)/"output",
                      sources=["burlington_project_pages"],
                      burlington_urls=[cue.BURLINGTON_PROJECT_URLS[0]])
            self.assertEqual(cue.run(**opts,
                session=Session({cue.BURLINGTON_PROJECT_URLS[0]:BURLINGTON_HTML}),observed="2026-10-24"),0)
            self.assertEqual(cue.run(**opts,session=Session({}),observed="2026-10-25"),1)
            conn=sqlite3.connect(Path(d)/"data"/"early_cues_review.sqlite")
            self.assertEqual(conn.execute("select count(*) from snapshots").fetchone()[0],1)
            self.assertEqual(conn.execute("select count(*) from changes").fetchone()[0],0)
            conn.close()

    def test_refuse_external_urls(self):
        with self.assertRaises(ValueError):
            cue.fetch_html(Session({}),"https://malicious.invalid/example")
        with self.assertRaises(ValueError):
            cue.fetch_html(Session({}),"http://www.ieso.ca/")

if __name__=="__main__":
    unittest.main()
