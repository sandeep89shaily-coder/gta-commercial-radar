"""Regressions from the November 9 integrated Radar export (without personal licence data)."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gta_commercial_activation_pilot as activation
import gta_discovery_run as discovery


class TorontoLicenceSchemaTests(unittest.TestCase):
    def test_published_mls_column_names_are_not_treated_as_missing_address(self):
        source = {
            "source": "toronto_business_licences", "key": "LIC-TEST-1",
            "first_seen": "2026-11-09T10:00:00Z",
            "sha": "fixture-source-hash", "raw": {
                "Category": "EATING OR DRINKING ESTABLISHMENT",
                "Licence No": "LIC-TEST-1",
                "Operating Name": "Test Restaurant",
                "Issued": "2026-11-06",
                "Licence Address Line 1": "100 Queen Street West",
                "Licence Address Line 2": "Toronto, ON",
                "Cancel Date": "",
            }
        }
        row, reason = activation.classify(source, dt.date(2026, 11, 9), 120)
        self.assertIsNone(reason)
        self.assertEqual(row["site_address"], "100 Queen Street West")
        self.assertEqual(row["business_name"], "Test Restaurant")
        self.assertEqual(row["source_event_date"], "2026-11-06")
        self.assertEqual(row["activation_stage"],
                         "LICENCE_ISSUED_NOT_OPENING_CONFIRMED")
        self.assertEqual(row["opening_confirmed"], "NO")
        self.assertEqual(row["buyer_verified"], "NO")
        self.assertEqual(row["purchasing_status"], "UNKNOWN")

    def test_cancel_date_and_old_issued_are_not_new_opening(self):
        fixture = {
            "source":"toronto_business_licences","key":"L2",
            "first_seen":"2026-11-09", "sha":"h",
            "raw":{"Category":"EATING OR DRINKING ESTABLISHMENT",
                   "Licence Address Line 1":"150 Bay Street",
                   "Issued":"2026-11-08","Cancel Date":"2026-11-09"}}
        self.assertEqual(activation.classify(fixture,dt.date(2026,11,9),120)[1],
                         "TERMINAL_OR_RENEWED_LICENCE")
        fixture["raw"]["Cancel Date"] = ""
        fixture["raw"]["Issued"] = "2020-04-01"
        self.assertEqual(activation.classify(fixture,dt.date(2026,11,9),120)[1],
                         "OUTSIDE_SOURCE_DATE_WINDOW")


class CollectorPartialSourceTests(unittest.TestCase):
    def _run(self, integrated):
        with tempfile.TemporaryDirectory() as td:
            ws=Path(td)
            results=ws/"GTA_RADAR_RESULTS"
            results.mkdir()
            target=results/discovery.WATCH
            class Outcome:
                returncode=0
            def collector(cmd, **kwargs):
                target.write_text("fresh daily export\n",encoding="utf-8")
                return Outcome()
            def preflight(*args,**kwargs):
                return {"ok":True,"status":"OK_UP_TO_DATE",
                        "installed_commit":"test"}
            def manual(_):
                return {"new_or_changed_source_records":144,
                        "initial_public_contact_hints":0,
                        "manual_review_csv":"path.csv",
                        "manual_review_html":"path.html"}
            with patch.object(discovery,"find_workspace",return_value=ws):
                code=discovery.execute(ws,runner=collector,preflight=preflight,
                        list_builder=manual,integrator=lambda *_args,**_kwargs:integrated)
            status=json.loads((results/"GTA_RADAR_DISCOVERY_RUN_STATUS.json").
                              read_text(encoding="utf-8"))
            return code,status

    def test_blocked_optional_meeting_source_preserves_collection_success(self):
        code,status=self._run({
            "status":"PARTIAL_REVIEW_REQUIRED",
            "blocked_sources":["meeting_vaughan"],
            "failed_stages":[],
            "combined_records":216})
        self.assertEqual(code,0)
        self.assertTrue(status["completed"])
        self.assertTrue(status["meeting_document_pipeline_complete"])
        self.assertTrue(status["review_source_coverage_partial"])
        self.assertEqual(status["status"],
                         "INTEGRATED_INTELLIGENCE_READY_WITH_BLOCKED_SOURCES")
        self.assertEqual(status["integrated_intelligence"]["blocked_sources"],
                         ["meeting_vaughan"])

    def test_real_failed_processing_is_not_reported_as_success(self):
        code,status=self._run({
            "status":"PARTIAL_REVIEW_REQUIRED",
            "blocked_sources":["meeting_vaughan"],
            "failed_stages":["verified_source_processing"]})
        self.assertEqual(code,2)
        self.assertFalse(status["completed"])
        self.assertFalse(status["meeting_document_pipeline_complete"])
        self.assertEqual(status["status"],"INTEGRATED_PARTIAL_REVIEW_REQUIRED")


if __name__=="__main__":
    unittest.main()
