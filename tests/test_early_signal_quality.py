"""Offline checks: no API keys, desktop network or V8 database."""
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from early_signal_quality import (
    QUALITY_VERSION, app_key, classify, export_project_reports,
    parse_source_date, source_date
)


class QualityTests(unittest.TestCase):
    def test_arcgis_ms_as_number_and_string(self):
        ms = 1792000000000
        expected = dt.datetime.fromtimestamp(ms/1000, dt.timezone.utc).date().isoformat()
        self.assertEqual(parse_source_date(ms), expected)
        self.assertEqual(parse_source_date(str(ms)), expected)
        self.assertEqual(parse_source_date("2026-10-20"), "2026-10-20")
        self.assertEqual(parse_source_date("2026/10/20"), "2026-10-20")
        self.assertEqual(parse_source_date("10/20/2026"), "2026-10-20")

    def test_dates_not_invented_from_invalid_values(self):
        for val in (None, "", "0", "42", "99999", "9644-11-20", "3026-01-01"):
            self.assertEqual(parse_source_date(val), "", val)
        self.assertEqual(source_date({"DATE_RECEIVED": None}, ["DATE_RECEIVED"]),
                         ("", "MISSING_OR_INVALID_SOURCE_DATE"))

    def test_energy_and_loading_docks_are_commercial(self):
        self.assertEqual(classify("Energy-from-waste facility redevelopment"),
                         "POSSIBLE_COMMERCIAL")
        self.assertEqual(classify("Addition of 15 loading docks"), "POSSIBLE_COMMERCIAL")
        self.assertEqual(classify("Proposed 22-unit residential condominium"),
                         "RESIDENTIAL_LIKELY")
        self.assertEqual(classify("Commercial offices with residential apartments"),
                         "MIXED_USE_REVIEW")
        self.assertEqual(classify("12 storey housing"), "USE_UNKNOWN")
        self.assertEqual(classify("Site Plan", {"ICI_INDUST": 3000}),
                         "POSSIBLE_COMMERCIAL")
        self.assertEqual(classify("Non-residential manufacturing plant"),
                         "POSSIBLE_COMMERCIAL")

    def test_york_gis_ids_are_not_assumed_application_numbers(self):
        a = {"source_id": "york_region_development", "application_id": "12",
             "feature_id": "10012"}
        b = {"source_id": "toronto_development", "application_id": "26 10012",
             "feature_id": "10012"}
        self.assertIn("GIS_FEATURE", app_key(a))
        self.assertIn("APP|", app_key(b))

    def test_cross_stage_links_require_same_address_not_just_company(self):
        from early_signal_quality import possible_stage_links
        a = {"source_id":"brampton_preconsultation", "stage":"PRE_CONSULTATION",
             "city":"Brampton", "location":"350 MAIN STREET NORTH",
             "source_application_date":"2026-01-10",
             "project_group_key":"PRE:123", "application_id":"PRE-123"}
        b = {"source_id":"brampton_site_plans", "stage":"SITE_PLAN",
             "city":"Brampton", "location":"350 Main St N Brampton ON",
             "source_application_date":"2026-10-10",
             "project_group_key":"SPA:456", "application_id":"SPA-456"}
        linked = possible_stage_links([a, b], dt.date(2026,10,24))
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["link_confidence"],
                         "POSSIBLE_SHARED_ADDRESS_AND_TIMELINE")
        self.assertEqual(possible_stage_links(
            [a, {**b,"location":"400 Main St N"}], dt.date(2026,10,24)), [])

    def test_group_multi_features_without_erasing_first_seen(self):
        with tempfile.TemporaryDirectory() as directory:
            db = sqlite3.connect(":memory:")
            db.execute("CREATE TABLE observations (source_id TEXT,first_seen TEXT,content TEXT)")
            common = {
                "source_id": "toronto_development", "city": "Toronto", "stage": "PLANNING",
                "application_id": "26123456", "source_application_date": "2026-10-10",
                "source_date_basis": "INDATE", "status": "Review",
                "description": "Industrial expansion and loading dock",
                "commercial_signal": "POSSIBLE_COMMERCIAL", "source_url": "https://example.org",
                "published_company_unverified_role": "", "company_role": "COMPANY_UNKNOWN",
            }
            for number, when, location in ((1, "2026-10-24T12:00:00+00:00", "10 Main St"),
                                           (2, "2026-10-25T12:00:00+00:00", "12 Main St")):
                row = {**common, "feature_id":str(number), "location":location}
                db.execute("INSERT INTO observations VALUES (?,?,?)",
                           ("toronto_development", when, json.dumps(row)))
            data = export_project_reports(db, Path(directory), today=dt.date(2026,10,25))
            self.assertEqual(data["review_candidates"], 1)
            audit = data["source_stats"][0]
            self.assertEqual(audit["project_groups"], 1)
            self.assertEqual(audit["multi_feature_groups"], 1)
            text = (Path(directory)/"EARLY_SIGNALS_PROJECTS_REVIEW_ONLY.csv").read_text(
                encoding="utf-8-sig")
            self.assertIn("MULTIPLE_SITE_FEATURES_REVIEW", text)
            self.assertIn("2026-10-24T12:00:00", text)


if __name__ == "__main__":
    unittest.main()
