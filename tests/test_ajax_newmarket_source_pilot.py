"""Offline source adapter tests; never call Ajax/Newmarket or spend AI money."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from gta_ajax_newmarket_source_pilot import parse, query, write, SOURCES

def feature(**attrs):
    return {"attributes": attrs}

class AjaxNewmarketAdapters(unittest.TestCase):
    def test_ajax_real_reference_only_and_preconsultation_not_publication(self):
        data = {"features": [
            feature(OBJECTID=1, REF_ID="SPA-26-004", ADDRESS="12 Industry Road",
                    DESCRIPTION="Proposed industrial plant expansion",
                    APPLICANT="Example Industries", TYPE="Industrial",
                    STATUS="Active", APP_SUBTYPE=1, SUBMISSION_DATE=1794441600000),
            feature(OBJECTID=2, REF_ID="", ADDRESS="22 Fake Street",
                    DESCRIPTION="Warehouse", TYPE="Industrial"),
            feature(OBJECTID=3, REF_ID="SPA-26-004", ADDRESS="12 Industry Road",
                    DESCRIPTION="Duplicate parcel", TYPE="Industrial"),
        ]}
        rows = parse("Ajax", data)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["application_id"], "SPA-26-004")
        self.assertEqual(row["record_status"], "COMMERCIAL_SCOPE_REVIEW_ONLY")
        self.assertEqual(row["source_date_basis"],
                         "APPLICATION_SUBMITTED_NOT_PUBLICATION")
        self.assertEqual(row["original_publication_verified"], "False")
        self.assertEqual(row["buying_role_verified"], "False")
        self.assertEqual(row["open_supplier_package_verified"], "False")
        self.assertEqual(row["source_oid_for_diagnostics_only"], "1")

    def test_newmarket_floor_area_not_a_project_id_and_edit_date_not_publication(self):
        rows = parse("Newmarket", {"features": [
            feature(OBJECTID=9, FILE_NUM="D12-2026-009", LOCATION="20 Main Street",
                    DESCRIPTION="Proposed commercial shopping complex",
                    OWNER="Company Ltd", PROPOSE_LAND_USE="Commercial",
                    APP_STATUS="Pre-Application Submission", EDIT_WHEN=1794441600000),
            feature(OBJECTID=10, FILE_NUM=None, LOCATION="24 Main Street",
                    DESCRIPTION="Missing original file ID", PROPOSE_LAND_USE="Industrial"),
        ]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_date_basis"], "GIS_LAST_EDIT_NOT_PUBLICATION")
        self.assertEqual(rows[0]["current_status"], "Pre-Application Submission")

    def test_query_caps_pagination_and_uses_no_geometry(self):
        pages = []
        def fetch(url):
            pages.append(url)
            if "resultOffset=0" in url:
                return {"features":[feature(OBJECTID=i+1,REF_ID=f"SPA-{i+1}",
                    ADDRESS=f"{i+1} Factory Road",DESCRIPTION="Industrial site",
                    TYPE="Industrial") for i in range(100)]}
            return {"features":[feature(OBJECTID=101,REF_ID="SPA-101",
                ADDRESS="101 Factory Road",DESCRIPTION="Industrial site",
                TYPE="Industrial")]}
        rows = query("Ajax", fetcher=fetch, max_rows=150, robots_check=False)
        self.assertEqual(len(rows), 101)
        self.assertEqual(len(pages), 2)
        self.assertIn("returnGeometry=false",pages[0])
        self.assertIn("resultRecordCount=50",pages[1])
        self.assertIn("resultOffset=100",pages[1])

    def test_duplicate_oid_across_pages_fails_closed(self):
        def fetch(url):
            return {"features":[feature(OBJECTID=i+1 if "resultOffset=0" in url
               else 1, REF_ID=f"SPA-{i}", ADDRESS="10 Industry Rd",
               DESCRIPTION="Industrial plant", TYPE="Industrial") for i in range(
                   100 if "resultOffset=0" in url else 50)]}
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OBJECTID"):
            query("Ajax",fetcher=fetch,max_rows=150,robots_check=False)

    def test_source_error_and_invalid_shape_are_not_success(self):
        with self.assertRaisesRegex(ValueError,"ARCGIS_ERROR"):
            parse("Ajax",{"error":{"code":403}})
        with self.assertRaisesRegex(ValueError,"FEATURES_ARRAY_REQUIRED"):
            parse("Newmarket",{"features":None})
        with self.assertRaises(ValueError):
            query("Ajax",max_rows=1000,robots_check=False)

    def test_isolated_output_and_no_purchasing_claim(self):
        rows = parse("Newmarket",{"features":[feature(OBJECTID=5,
            FILE_NUM="D-21-1", LOCATION="30 Old Road",
            DESCRIPTION="New industrial production line",PROPOSE_LAND_USE="Industrial",
            APP_STATUS="Under Review")]})
        with tempfile.TemporaryDirectory() as tmp:
            result=write(tmp,rows,modes={"Newmarket":"OFFLINE_APPROVED_SNAPSHOT"})
            self.assertEqual(result["candidate_rows"],1)
            self.assertTrue(result["production_municipalities_unchanged"])
            self.assertEqual(result["verified_buyers"],0)
            self.assertFalse((Path(tmp)/"v5_ai_budget.sqlite").exists())
            with (Path(tmp)/"GTA_RADAR_AJAX_NEWMARKET_RESEARCH_APPLICATIONS.csv"
                  ).open(encoding="utf-8-sig") as fp:
                saved=list(csv.DictReader(fp))
            self.assertEqual(saved[0]["source_date"],"")
            self.assertEqual(saved[0]["buying_role_verified"],"False")

if __name__ == "__main__":
    unittest.main()
