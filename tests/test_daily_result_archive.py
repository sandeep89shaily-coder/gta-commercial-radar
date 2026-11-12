"""Dated integrated Radar archive: data preserved, untrusted claims excluded."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import gta_daily_result_archive as archive


class DatedManualResultsArchiveTests(unittest.TestCase):
    def _workspace(self,root,*,fresh=True,failed=None):
        results=root/"GTA_RADAR_RESULTS"
        out=results/"MONDAY_FULL_RADAR"
        out.mkdir(parents=True)
        (out/"MONDAY_FULL_RADAR_STATUS.json").write_text(json.dumps({
            "mode":"MANUAL_COMPLETE_RADAR_REVIEW","started_utc":"2026-11-11T13:00:00Z",
            "collection_performed":True,"fresh_collection_verified":fresh,
            "failed_stages":failed or [],
            "status":"ALL_STAGES_RAN_REVIEW_ONLY" if not failed else "REVIEW_COMPLETED_WITH_FAILURES"
        }))
        (out/"MONDAY_FULL_RADAR_REPORT.html").write_text("<html><body>Review only</body></html>")
        (results/"GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json").write_text('{"seen":{"a":"sha"}}')
        (results/"GTA_RADAR_SOURCE_KEY.json").write_text('{"status":"INDETERMINATE"}')
        (results/"GTA_RADAR_SECRET_TOKEN.json").write_text('{"token":"SHOULD_NOT_LEAVE_MACHINE"}')
        (results/"radar.sqlite").write_bytes(b"database-secret")
        (out/"LOGS").mkdir()
        (out/"LOGS"/"access.log").write_text("SUPERSECRET")
        (results/"INDUSTRIAL_PILOT").mkdir()
        (results/"INDUSTRIAL_PILOT"/"GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv").write_text(
            "ero_number,buyer_verified\n026-1021,NO\n")
        (results/"COMMERCIAL_ACTIVATION_PILOT").mkdir()
        (results/"COMMERCIAL_ACTIVATION_PILOT"/"GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv").write_text(
            "signal_id,opening_confirmed\na,NO\n")
        return results

    def test_one_manual_run_has_safe_dated_package_and_hash_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            results=self._workspace(root)
            when=dt.datetime(2026,11,11,9,15,31,tzinfo=dt.timezone.utc)
            report=archive.create(results,now=when)
            location=Path(report["archive"])
            self.assertEqual(location.parent,root/"GTA_RADAR_EXPORTS")
            self.assertEqual(location.name,"GTA_RADAR_RESULTS_2026-11-11_091531.zip")
            self.assertEqual(report["freshness_gate"],
                             "FRESH_COLLECTION_EXECUTION_REPORTED_NOT_SOURCE_VERIFICATION")
            with zipfile.ZipFile(location) as z:
                files=set(z.namelist())
                self.assertIn(archive.MANIFEST,files)
                self.assertIn("GTA_RADAR_RESULTS/GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json",files)
                self.assertIn("GTA_RADAR_RESULTS/MONDAY_FULL_RADAR/MONDAY_FULL_RADAR_STATUS.json",files)
                self.assertIn("GTA_RADAR_RESULTS/INDUSTRIAL_PILOT/GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv",files)
                self.assertIn("GTA_RADAR_RESULTS/COMMERCIAL_ACTIVATION_PILOT/GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv",files)
                self.assertFalse(any("sqlite" in x or "SECRET_TOKEN" in x or "access.log" in x
                                     for x in files))
                manifest=json.loads(z.read(archive.MANIFEST))
                evidence={x["path"]:x["sha256"] for x in manifest["file_inventory"]}
                observed=z.read("GTA_RADAR_RESULTS/GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json")
                self.assertEqual(evidence["GTA_RADAR_RESULTS/GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json"],
                                 hashlib.sha256(observed).hexdigest())
                self.assertFalse(manifest["buyer_verified"])
                self.assertFalse(manifest["actual_business_openings_verified"])
                self.assertFalse(manifest["open_supplier_package_verified"])
                self.assertEqual(manifest["accepted_commercial_leads"],0)
            self.assertEqual((results/"radar.sqlite").read_bytes(),b"database-secret")

    def test_partial_collection_still_exports_diagnostics_not_freshness(self):
        with tempfile.TemporaryDirectory() as td:
            results=self._workspace(Path(td),fresh=False,failed=["daily_radar"])
            r=archive.create(results)
            self.assertEqual(r["freshness_gate"],
                             "PARTIAL_OR_SAVED_EVIDENCE_ONLY_NOT_FRESH_VERIFIED")
            with zipfile.ZipFile(r["archive"]) as z:
                m=json.loads(z.read(archive.MANIFEST))
                self.assertEqual(m["stage_failures"],["daily_radar"])

    def test_source_warnings_dont_masquerade_as_complete_municipal_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            results=self._workspace(Path(td))
            status=results/"MONDAY_FULL_RADAR"/"MONDAY_FULL_RADAR_STATUS.json"
            manifest=json.loads(status.read_text())
            manifest["optional_source_warnings"]={
                "optional_failed_stages":["guelph_official_gis"],
                "blocked_sources":["meeting_vaughan"],"details":[]}
            manifest["status"]="ALL_STAGES_RAN_WITH_SOURCE_WARNINGS_REVIEW_ONLY"
            status.write_text(json.dumps(manifest),encoding="utf-8")
            archive_result=archive.create(results)
            self.assertEqual(archive_result["freshness_gate"],
                             "FRESH_COLLECTION_EXECUTION_WITH_PARTIAL_SOURCES_NOT_VERIFIED")
            with zipfile.ZipFile(archive_result["archive"]) as z:
                out=json.loads(z.read(archive.MANIFEST))
            self.assertEqual(out["optional_source_warnings"]["blocked_sources"],
                             ["meeting_vaughan"])
            self.assertEqual(out["stage_failures"],[])

    def test_missing_or_invalid_original_run_status_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as td:
            results=Path(td)/"GTA_RADAR_RESULTS"
            results.mkdir()
            with self.assertRaisesRegex(ValueError,"NO_FULL_INTEGRATED_RUN_MANIFEST"):
                archive.create(results)
            folder=results/"MONDAY_FULL_RADAR"
            folder.mkdir()
            (folder/"MONDAY_FULL_RADAR_STATUS.json").write_text('{"mode":"wrong"}')
            with self.assertRaisesRegex(ValueError,"WRONG_RUN_MANIFEST_TYPE"):
                archive.create(results)

    def test_same_second_never_overwrites_existing_review_zip(self):
        with tempfile.TemporaryDirectory() as td:
            results=self._workspace(Path(td))
            now=dt.datetime(2026,11,11,9,15,31)
            old=Path(archive.create(results,now=now)["archive"])
            original=old.read_bytes()
            with self.assertRaisesRegex(FileExistsError,"ARCHIVE_ALREADY_EXISTS"):
                archive.create(results,now=now)
            self.assertEqual(old.read_bytes(),original)


if __name__ == "__main__":
    unittest.main()
