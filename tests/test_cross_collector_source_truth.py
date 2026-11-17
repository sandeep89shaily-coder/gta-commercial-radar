"""Cross-collector source failures must survive successful parallel HTML feeds."""
from __future__ import annotations
import csv
import json
import tempfile
import unittest
from pathlib import Path
from gta_collection_truth import build as collection
from gta_cross_collector_health import extra_source_failures, build as cross
from gta_city_coverage_report import build as city_coverage
from gta_source_quality_v1 import build as source_quality

MISS = ("COUNCIL_INTELLIGENCE_REVIEW/MISSISSAUGA_OFFICIAL_GIS_SOURCE_AUDIT/"
        "MISSISSAUGA_OFFICIAL_GIS_SOURCE_AUDIT.json")
BRAMP = ("COUNCIL_INTELLIGENCE_REVIEW/BRAMPTON_OFFICIAL_GIS_PLANNING/"
         "BRAMPTON_OFFICIAL_GIS_SOURCE_STATUS.json")


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def csv_write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class SourceHealthTruthTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        write(self.root/MISS, {"layers":[
          {"layer":"SITE_PLAN", "status":"SOURCE_HELD",
           "reason":"PermissionError:ROBOTS_DENIED"},
          {"layer":"REZONING", "status":"SOURCE_HELD",
           "reason":"PermissionError:ROBOTS_DENIED"}]})
        write(self.root/BRAMP, {"layer_results":[
          {"layer":9, "name":"OPA_ZBA_SUBDIVISION",
           "status":"SOURCE_FAILED_PRIOR_HISTORY_PRESERVED",
           "reason":"PermissionError:ARCGIS_ROBOTS_ACCESS_DENIED"},
          {"layer":10, "name":"PRE_CONSULTATION",
           "status":"SOURCE_FAILED_PRIOR_HISTORY_PRESERVED",
           "reason":"PermissionError:ARCGIS_ROBOTS_ACCESS_DENIED"},
          {"layer":11, "name":"SITE_PLAN_APPROVAL",
           "status":"SOURCE_FAILED_PRIOR_HISTORY_PRESERVED",
           "reason":"PermissionError:ARCGIS_ROBOTS_ACCESS_DENIED"}]})
        csv_write(self.root/"GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv", [{
            "project_id":"MID", "city":"Mississauga",
            "application_id":"OZ 26-15 W5",
            "description":"Industrial warehouse construction",
            "record_source_url":"https://www.mississauga.ca/planning/123",
            "source_record_date":"", "observation":"UNCHANGED"}])

    def test_blocked_gis_is_not_erased_by_working_html(self):
        audit=collection(self.root)
        miss=next(x for x in audit["per_city"] if x["city"]=="Mississauga")
        self.assertEqual(miss["application_files"], 1)
        self.assertEqual(miss["source_failures"], 2)
        self.assertEqual(miss["access_failures"], 2)
        self.assertEqual(miss["quality_status"],
                         "PARTIAL_APPLICATION_RECORDS_WITH_SOURCE_FAILURES")
        bramp=next(x for x in audit["per_city"] if x["city"]=="Brampton")
        self.assertEqual(bramp["source_failures"], 3)
        self.assertEqual(bramp["access_failures"], 3)
        self.assertEqual(audit["new_or_changed_commercial_manual_review"], 0)
        quality=source_quality(self.root)
        self.assertGreaterEqual(quality["municipalities_with_source_access_failures"],2)

    def test_coverage_report_says_parallel_source_blocked(self):
        result=city_coverage(self.root,
            {"city_status":[{"city":"Mississauga", "fetch_status":"INDEX_FETCHED",
                             "actual_application_rows":30}]},
            {},{},{} )
        miss=next(x for x in result["city_status"] if x["city"]=="Mississauga")
        self.assertEqual(miss["html_application_rows"],30)
        self.assertEqual(miss["measured_source_state"],
                         "PARTIAL_APPLICATION_CANDIDATES_PARALLEL_GIS_BLOCKED")
        self.assertIn("MISSISSAUGA_OFFICIAL_GIS_AUDIT",miss["source_details"])

    def test_cross_report_does_not_double_count_fixed_consolidation(self):
        collection(self.root)
        report=cross(self.root)
        miss=next(x for x in report["per_city"] if x["city"]=="Mississauga")
        self.assertEqual(miss["reconciled_source_failures"],2)
        self.assertEqual(miss["reconciled_access_failures"],2)
        self.assertEqual(miss["extra_council_gis_failures"],2)

    def test_meeting_failures_count_when_planning_source_succeeds(self):
        write(self.root/"GTA_RADAR_INTEGRATED_INTELLIGENCE_STATUS.json", {
            "stages": [
                {"stage":"meeting_oakville", "status":"FAILED",
                 "error":"SSL: CERTIFICATE_VERIFY_FAILED"},
                {"stage":"meeting_vaughan", "status":"BLOCKED",
                 "error":"Official meeting source returned HTTP 403 Forbidden"}]})
        output=collection(self.root)
        oakville=next(x for x in output["per_city"] if x["city"]=="Oakville")
        vaughan=next(x for x in output["per_city"] if x["city"]=="Vaughan")
        self.assertGreaterEqual(oakville["source_failures"],1)
        self.assertGreaterEqual(vaughan["access_failures"],1)

    def test_short_dated_official_record_not_lost_to_longer_source(self):
        csv_write(self.root/"GTA_RADAR_GUELPH_GIS_APPLICATIONS.csv", [{
            "project_id":"GIS:G1", "city":"Guelph", "application_id":"OZS26-021",
            "description":"Industrial warehouse",
            "source_record_date":"2026-11-13",
            "source_record_date_basis":"OFFICIAL_GIS_INDATE_NOT_FIRST_PUBLICATION",
            "source_url":"https://guelph.ca/notice/21",
            "observation":"UNCHANGED"}])
        csv_write(self.root/"GTA_RADAR_MUNICIPAL_PROJECT_FEED.csv", [{
            "project_id":"HTML:G1", "city":"Guelph", "application_id":"OZS26-021",
            "description":"Industrial warehouse manufacturing plant with additional "
                          "office support and extended loading dock",
            "source_url":"https://guelph.ca/development/21",
            "observation":"UNCHANGED"}])
        report=collection(self.root)
        with (self.root/"GTA_RADAR_COLLECTION_MASTER.csv").open(
                encoding="utf-8-sig",newline="") as fp:
            rows=list(csv.DictReader(fp))
        guelph=next(x for x in rows if x["city"]=="Guelph" and
                    x["application_id"]=="OZS26-021")
        self.assertEqual(guelph["date"],"2026-11-13")
        self.assertEqual(guelph["date_basis"],
                         "OFFICIAL_GIS_INDATE_NOT_FIRST_PUBLICATION")
        self.assertEqual(report["new_or_changed_commercial_manual_review"],0)

    def test_missing_other_source_files_do_not_invent_success(self):
        self.assertEqual(len(extra_source_failures(self.root)["Mississauga"]),2)
        self.assertEqual(len(extra_source_failures(self.root)["Brampton"]),3)


if __name__ == "__main__":
    unittest.main()
