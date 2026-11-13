"""Offline completeness and continuity checks for Mississauga GIS records."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_mississauga_official_gis_source_audit import LAYERS, NAMES, REQUIRED
from gta_mississauga_official_gis_records import run, CSV, LEDGER, TWENTY, STATUS

AT = dt.datetime(2026, 11, 13, 20, tzinfo=dt.timezone.utc)


def source_records(url, params, *, broken=None, description="Proposed industrial warehouse"):
    base = url.removesuffix("/query")
    layer = next(key for key, value in LAYERS.items() if value == base)
    if not url.endswith("/query"):
        return {"name": NAMES[layer], "objectIdField": "OBJECTID",
                "fields": [{"name": key} for key in REQUIRED]}
    if params.get("returnIdsOnly") == "true":
        return {"objectIds": [1, 2]}
    if broken == layer:
        return {"features": [{"attributes": {"OBJECTID": 1}}]}
    return {"features": [{"attributes": {
        "OBJECTID": i, "APP_FILE_NO": f"SP 26-{i}" if layer == "SITE_PLAN"
        else f"OZ 26-{i}",
        "SITE_ADDRESS": f"{i} Example Road",
        "DESCRIPTION": description, "APPLICATION_DATE": 1790000000000,
        "APPROVAL_DATE": None, "APPLICANT": "Example Corporation",
        "SIMPLE_STATUS": "In process", "TOTAL_NON_RES_GFA": 1000,
        "ICI_INDUST": 900, "ICI_OFFICE": 0, "ICI_RETAIL": 0,
    }} for i in [1, 2]]}


class MississaugaRecordsTests(unittest.TestCase):
    def test_manual_default_is_no_network(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run(folder)
            self.assertEqual(result["status"], "FETCH_NOT_REQUESTED")
            self.assertEqual(result["paid_ai_calls"], 0)

    def test_full_inventory_and_exact_review_records(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run(folder, fetch=True, now=AT, fetcher=source_records)
            self.assertEqual(result["status"], "BOTH_LAYERS_REVIEW_ONLY")
            self.assertEqual(result["current_application_files"], 4)
            self.assertEqual(result["cases_for_manual_audit"], 4)
            self.assertEqual(result["buyers_verified"], 0)
            with (Path(folder) / CSV).open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row["date_basis"] ==
                "GIS_APPLICATION_DATE_NOT_FIRST_PUBLICATION" for row in rows))
            self.assertTrue((Path(folder) / TWENTY).exists())

    def test_second_run_preserves_first_seen(self):
        with tempfile.TemporaryDirectory() as folder:
            first = run(folder, fetch=True, now=AT, fetcher=source_records)
            later = AT + dt.timedelta(days=1)
            second = run(folder, fetch=True, now=later, fetcher=source_records)
            self.assertEqual(second["changed_records_review_only"], 0)
            history = json.loads((Path(folder) / LEDGER).read_text())["items"]
            self.assertTrue(all(v["first_observed_utc"] == AT.isoformat()
                                for v in history.values()))

    def test_partial_source_failure_preserves_history(self):
        with tempfile.TemporaryDirectory() as folder:
            run(folder, fetch=True, now=AT, fetcher=source_records)
            before = json.loads((Path(folder) / LEDGER).read_text())["items"]
            def broken(url, params):
                return source_records(url, params, broken="REZONING")
            result = run(folder, fetch=True, now=AT + dt.timedelta(days=1),
                         fetcher=broken)
            self.assertEqual(result["status"], "PARTIAL_OFFICIAL_GIS_REVIEW_ONLY")
            self.assertEqual(result["layers_complete"], 1)
            after = json.loads((Path(folder) / LEDGER).read_text())["items"]
            self.assertEqual(set(before), set(after))
            self.assertEqual(after["REZONING:OZ 26-1"], before["REZONING:OZ 26-1"])

    def test_both_sources_fail_do_not_overwrite_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            run(folder, fetch=True, now=AT, fetcher=source_records)
            previous = (Path(folder) / CSV).read_bytes()
            def denied(url, params):
                raise PermissionError("HTTP_403")
            result = run(folder, fetch=True, now=AT + dt.timedelta(days=1),
                         fetcher=denied)
            self.assertEqual(result["status"], "NO_CURRENT_SOURCE_ROWS_HISTORY_PRESERVED")
            self.assertEqual((Path(folder) / CSV).read_bytes(), previous)
            self.assertEqual(json.loads((Path(folder) / STATUS).read_text())["layers_complete"], 0)

    def test_observed_content_changes_not_first_publications(self):
        with tempfile.TemporaryDirectory() as folder:
            run(folder, fetch=True, now=AT, fetcher=source_records)
            def changed(url, params):
                return source_records(url, params, description="Expanded industrial warehouse")
            result = run(folder, fetch=True, now=AT + dt.timedelta(days=1), fetcher=changed)
            self.assertEqual(result["changed_records_review_only"], 4)
            self.assertEqual(result["publisher_first_publications_verified"], 0)


if __name__ == "__main__":
    unittest.main()
