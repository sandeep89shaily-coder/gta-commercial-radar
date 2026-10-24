"""Source-conservative Hamilton early industrial ranking tests."""
import csv
import sqlite3
import tempfile
import json
import unittest
from pathlib import Path
import hamilton_industrial_triage as t
from early_cue_watch import db_setup,save_source

G={"source_id":"hamilton_applications_gis","record_id":"HAMILTON-GIS-15",
"title":"Formal Consultation: FC-26-044",
"site":"844 Glancaster Road, Ancaster","file_number":"FC-26-044",
"source_application_year":"2026","stage":"FORMAL_CONSULTATION",
"description":"Industrial warehousing distribution and stormwater works",
"commercial_fit":"POSSIBLE_COMMERCIAL",
"procurement_status":"UNKNOWN","source_url":"https://services.arcgis.com/example"}
N={"source_id":"hamilton_planning_notices","record_id":"/complete-application",
"title":"Complete Application for 844 Glancaster Road",
"site":"844 Glancaster Road, Ancaster","file_number":"FC-26-044",
"source_date":"2026-05-11","date_basis":"OFFICIAL_NOTICE_PUBLISHED_DATE",
"company":"Alba Developments","source_url":"https://www.hamilton.ca/notice",
"commercial_fit":"POSSIBLE_COMMERCIAL","procurement_status":"UNKNOWN"}

class Tests(unittest.TestCase):
    def test_strict_civic_address(self):
        self.assertEqual(t.address_key("844 Glancaster Road, Ancaster"),"844 GLANCASTER RD")
        self.assertEqual(t.address_key("844-846 Glancaster Road"),"")
        self.assertEqual(t.address_key("No address"),"")
        self.assertEqual(t.file_key("FC-26-044"),"FC-26-044")

    def test_official_file_match_proves_document_link_not_buyer(self):
        rows=t.evaluate([G],[N])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["notice_posted_date"],"2026-05-11")
        self.assertEqual(rows[0]["notice_published_applicant"],"Alba Developments")
        self.assertEqual(rows[0]["vendor_selection_status"],"UNKNOWN")
        self.assertEqual(rows[0]["sale_readiness"],"NOT_SALE_READY")
        self.assertEqual(rows[0]["file_identity_match"],"MATCHED_OFFICIAL_FILE_NUMBER_REVIEW")
        self.assertIn("INFRASTRUCTURE",rows[0]["potential_supplier_scopes"])

    def test_same_address_different_file_not_auto_matched(self):
        n={**N,"file_number":"DPA-2026-00043"}
        rows=t.evaluate([G],[n])
        self.assertEqual(rows[0]["notice_posted_date"],"")
        self.assertEqual(rows[0]["notice_published_applicant"],"")
        self.assertEqual(rows[0]["file_identity_match"],"NOT_MATCHED_BY_FILE")
        self.assertIn("hamilton.ca",rows[0]["address_only_possible_links"])

    def test_residential_penalty_and_historical_limit(self):
        home={**G,"record_id":"HAMILTON-GIS-17",
              "description":"New residential townhouse development",
              "commercial_fit":"RESIDENTIAL_LIKELY"}
        self.assertEqual(len(t.evaluate([home],[])),0)
        mixed={**G,"description":"Industrial warehouse and townhouse project"}
        self.assertLess(t.evaluate([mixed],[])[0]["research_score"],
                        t.evaluate([G],[])[0]["research_score"])
        old={**G,"source_application_year":"2022"}
        self.assertEqual(t.evaluate([old],[]),[])

    def test_readonly_database_and_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            dbfile=root/"hamilton.sqlite"
            db=sqlite3.connect(dbfile);db_setup(db)
            # Initial import yields no NEW event, but triage can assess history.
            save_source(db,"hamilton_applications_gis",[G],"2026-10-24T14:00:00Z")
            save_source(db,"hamilton_planning_notices",[N],"2026-10-24T14:00:00Z")
            db.close()
            self.assertEqual(t.run(dbfile,root/"out",limit=50),0)
            with (root/"out"/"HAMILTON_INDUSTRIAL_TRIAGE_REVIEW.csv").open(
                    encoding="utf-8-sig",newline="") as f:
                result=list(csv.DictReader(f))
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]["vendor_selection_status"],"UNKNOWN")
            db=sqlite3.connect(dbfile)
            self.assertEqual(db.execute("SELECT count(*) FROM changes").fetchone()[0],0)
            db.close()

if __name__=="__main__":unittest.main()
