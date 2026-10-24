"""Hamilton offline source and history tests. No live municipal queries."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse
import early_hamilton_watch as h

INDEX="""<html><body><main><h1>News Releases</h1>
<a href="/city-council/news-notices/news-releases/complete-application-844-glancaster-road-ancaster">
Complete Application for 844 Glancaster Road</a>
<a href="/city-council/news-notices/news-releases/complete-application-1310-south-service-road-stoney-creek">
Complete Application for 1310 South Service Road</a>
<a href="/city-council/news-notices/news-releases/waste-information">Other Hamilton news</a>
</main></body></html>"""

def notice(date="May 11, 2026",scope="create an industrial subdivision with warehousing"):
    return f"""<html><body><h1>Complete Application for 844 Glancaster Road, Ancaster</h1>
<h2>Published</h2><p>{date}</p>
<h2>Public Notice</h2><p>Notice of Complete Application</p>
<p>Proposal: The Applicant, Alba Developments is proposing to {scope}.</p>
<p>Address: 844 Glancaster Road, Ancaster (Ward 12)</p>
<p>File Number: DPA-2026-00043 and SUB-2026-00044</p>
<p>Application contact is a municipal planner, not supplier purchasing.</p></body></html>"""

class Reply:
    def __init__(self,obj):
        self.obj=obj
        self.text=obj if isinstance(obj,str) else ""
    def raise_for_status(self):pass
    def json(self):return self.obj

class S:
    def __init__(self,links):self.links=links
    def get(self,url,params=None,**kwargs):
        if url.endswith("/query"):
            if params.get("returnIdsOnly")=="true":
                return Reply({"objectIds":[1,2,3]})
            if params.get("objectIds")=="1,2":
                ids=[1,2]
            elif params.get("objectIds")=="3":ids=[3]
            else:raise AssertionError("Unrecognized ArcGIS batch")
            if self.links.get("drop_feature") and ids==[3]:
                return Reply({"features":[]})
            return Reply({"features":[{"attributes":{
                  "OBJECTID":i,
                  "FILE_NUM":"FC-25-040" if i==1 else f"DPA-2026-{i:05d}",
                  "FILE_TYPE":"Formal Consultation" if i==1 else "Zoning By-law Amendment",
                  "ADDRESS":"844 Glancaster Road",
                  "FILE_YEAR":2025 if i==1 else 2026,
                  "DESCRIP":"Warehouse manufacturing and industrial equipment"
            }} for i in ids]})
        if url==h.GIS:return Reply({"fields":[{"name":n} for n in (
            "OBJECTID","FILE_NUM","FILE_TYPE","ADDRESS","FILE_YEAR","DESCRIP")]})
        if url in self.links:return Reply(self.links[url])
        raise AssertionError("Unrecognized Hamilton URL: "+url)

class Tests(unittest.TestCase):
    def test_arcgis_complete_batches_and_date_provenance(self):
        rows=h.collect_gis(S({}),batch_size=2)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]["file_number"],"FC-25-040")
        self.assertEqual(rows[0]["stage"],"FORMAL_CONSULTATION")
        self.assertEqual(rows[0]["source_application_year"],"2025")
        self.assertEqual(rows[0]["source_date"],"")
        self.assertEqual(rows[0]["procurement_status"],"UNKNOWN")
        self.assertEqual(rows[1]["commercial_fit"],"POSSIBLE_COMMERCIAL")

    def test_partial_gis_rejected_not_rebased(self):
        with self.assertRaisesRegex(RuntimeError,"Partial GIS batch"):
            h.collect_gis(S({"drop_feature":True}),batch_size=2)

    def test_public_news_notice_and_original_publication(self):
        links=h.discover_notice_links(INDEX)
        self.assertEqual(len(links),2)
        url=next(iter(links))
        row=h.parse_notice_detail(notice(),url)
        self.assertEqual(row["source_date"],"2026-05-11")
        self.assertEqual(row["date_basis"],"OFFICIAL_NOTICE_PUBLISHED_DATE")
        self.assertEqual(row["file_number"],"DPA-2026-00043")
        self.assertEqual(row["company"],"Alba Developments")
        self.assertEqual(row["site"],"844 Glancaster Road, Ancaster")
        self.assertEqual(row["commercial_fit"],"POSSIBLE_COMMERCIAL")
        self.assertEqual(row["procurement_status"],"UNKNOWN")

    def test_residential_and_commercial_mix_only_review(self):
        self.assertEqual(h.fit("220 residential units and 50 retail units"),"MIXED_USE_REVIEW")
        self.assertEqual(h.fit("Townhouses and dwellings"),"RESIDENTIAL_LIKELY")

    def test_bad_html_does_not_create_zero_snapshot(self):
        with self.assertRaises(RuntimeError):
            h.discover_notice_links("<html><body>Access denied</body></html>")
        with self.assertRaises(RuntimeError):
            h.parse_notice_detail("<html><body>Not a notice</body></html>",
                                  "https://www.hamilton.ca/fake")

    def test_gis_first_baseline_and_stale_failed_notice(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            opts=dict(data_dir=p/"data",output_dir=p/"results",
                      sources=["hamilton_applications_gis"])
            self.assertEqual(h.run(**opts,session=S({}),
                                   observed="2026-10-24T16:30:00Z"),0)
            self.assertEqual(h.run(**opts,session=S({}),
                                   observed="2026-10-25T16:30:00Z"),0)
            db=sqlite3.connect(p/"data"/"early_hamilton_review.sqlite")
            self.assertEqual(db.execute("select count(*) from snapshots").fetchone()[0],3)
            self.assertEqual(db.execute("select count(*) from changes").fetchone()[0],0)
            db.close()
            self.assertEqual(h.run(**opts,session=S({"drop_feature":True}),
                                   observed="2026-10-26T16:30:00Z"),1)
            db=sqlite3.connect(p/"data"/"early_hamilton_review.sqlite")
            self.assertEqual(db.execute("select count(*) from snapshots").fetchone()[0],3)
            db.close()
            with (p/"results"/"EARLY_HAMILTON_SOURCE_STATUS.csv").open(
                      encoding="utf-8-sig",newline="") as fh:
                results=list(csv.DictReader(fh))
            self.assertEqual(results[0]["status"],"FAILED")

    def test_index_limited_to_visible_public_notices(self):
        links=h.discover_notice_links(INDEX)
        urls=list(links)
        s=S({h.NOTICES:INDEX,urls[0]:notice(),urls[1]:notice()})
        result,count=h.collect_notices(s,max_details=1)
        self.assertEqual(count,2)
        self.assertEqual(len(result),1)

if __name__=="__main__":
    unittest.main()
