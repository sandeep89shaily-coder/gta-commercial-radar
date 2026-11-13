"""Brampton official planning layer collector: complete provenance and fail closed."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_brampton_official_gis_planning import (
    run, BASE, LEDGER, ALL, CHANGED, STATUS, LAYERS, EXPECTED,
)

AT = dt.datetime(2026, 11, 13, 18, 0, tzinfo=dt.timezone.utc)
FIELD_LIST = [{"name": key} for key in EXPECTED]


def attributes(oid, file_id, *, purpose="Proposed industrial distribution warehouse",
               received=1793491200000):
    return {
        "POLY_ID": oid, "FILE_NUMBER": file_id, "LOCATION": "110 Test Road",
        "DATE_RECEIVED": received, "APPLICATION_TYPE": "Zoning amendment",
        "APPLICATION_TITLE": "Industrial warehouse proposal",
        "DESCRIPTION": purpose, "STATUS": "Under Review",
        "PROPOSAL_DESCRIPTION": "New logistics building",
        "AGENT_COMPANY": "Planning Studio Ltd",
        "APPLICANT_COMPANY": "Test Owner Inc",
    }


def source(*, failed=None, dropped=False, modified=False):
    calls = []
    def query(url, params):
        calls.append((url, dict(params)))
        number = int(url[len(BASE)+1:].split("/")[0])
        if number == failed:
            raise PermissionError("OFFICIAL_403")
        if url.endswith("/query"):
            if params.get("returnIdsOnly") == "true":
                return {"objectIds": [101, 103]}
            if params.get("objectIds"):
                ids = [int(x) for x in params["objectIds"].split(",")]
                result = [attributes(oid, f"OZS-2026-{number:02d}{oid}",
                                     purpose=("Updated commercial warehouse" if modified
                                              else "Proposed industrial distribution warehouse"))
                          for oid in ids]
                if dropped:
                    result.pop()
                return {"features": [{"attributes": a} for a in result]}
        return {"id": number, "name": {
            9: "OPA ZBA Subdivision",
            10: "Pre Consultation",
            11: "Site Plan Approval"
        }[number], "objectIdField": "POLY_ID",
                "fields": FIELD_LIST,
                "editingInfo": {"dataLastEditDate": 1793491200000}}
    return query, calls


class BramptonOfficialPlanningTests(unittest.TestCase):
    def test_all_three_layers_and_first_observed_is_not_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            query, calls = source()
            result = run(tmp, fetch=True, fetcher=query, now=AT)
            self.assertEqual(result["status"], "ALL_THREE_LAYERS_REVIEW_ONLY")
            self.assertEqual(result["layers_complete"], 3)
            self.assertEqual(result["applications_currently_extracted"], 6)
            self.assertEqual(result["first_observed_on_complete_layers"], 6)
            self.assertEqual(result["verified_first_publications"], 0)
            self.assertEqual(result["verified_buyers"], 0)
            self.assertEqual(result["paid_ai_calls"], 0)
            self.assertEqual(len(calls), 9)  # metadata, IDs, exact batch by layer
            self.assertTrue(all(
                call[1].get("returnGeometry") == "false"
                for call in calls if call[1].get("objectIds")))
            with (Path(tmp) / ALL).open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(row["application_id"].startswith("OZS-2026-")
                                for row in rows))
            self.assertTrue(all(
                row["date_received_basis"] == "GIS_DATE_RECEIVED_NOT_FIRST_PUBLICATION"
                for row in rows))
            self.assertTrue(all(row["buyer_verified"] == "False" for row in rows))
            self.assertEqual(
                len(json.loads((Path(tmp) / LEDGER).read_text())["items"]), 6)
            again = run(tmp, fetch=True, fetcher=query,
                        now=AT + dt.timedelta(days=1))
            self.assertEqual(again["first_observed_on_complete_layers"], 0)
            self.assertEqual(again["changed_application_records_review_only"], 0)

    def test_partial_city_layer_failure_preserves_held_layer_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            valid, _ = source()
            run(tmp, fetch=True, fetcher=valid, now=AT)
            previous = json.loads((Path(tmp) / LEDGER).read_text())
            broken, _ = source(failed=9, modified=True)
            result = run(tmp, fetch=True, fetcher=broken,
                         now=AT + dt.timedelta(days=1))
            self.assertEqual(result["status"], "PARTIAL_OFFICIAL_GIS_LAYERS_REVIEW_ONLY")
            self.assertEqual(result["layers_complete"], 2)
            self.assertEqual(result["applications_currently_extracted"], 4)
            current = json.loads((Path(tmp) / LEDGER).read_text())
            self.assertEqual(
                {k:v for k,v in previous["items"].items() if k.startswith("9:")},
                {k:v for k,v in current["items"].items() if k.startswith("9:")})
            self.assertTrue(any(
                r["status"] == "SOURCE_FAILED_PRIOR_HISTORY_PRESERVED"
                for r in result["layer_results"]))

    def test_incomplete_id_inventory_never_advances_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            incomplete, _ = source(dropped=True)
            result = run(tmp, fetch=True, fetcher=incomplete, now=AT)
            self.assertEqual(result["status"],
                             "ALL_OFFICIAL_GIS_LAYERS_HELD_NO_LEDGER_MUTATION")
            self.assertFalse((Path(tmp) / LEDGER).exists())
            self.assertFalse((Path(tmp) / ALL).exists())
            self.assertTrue(all("INCOMPLETE_BATCH" in x["reason"]
                                for x in result["layer_results"]))

    def test_changed_official_record_not_new_published_application(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = source()
            run(tmp, fetch=True, fetcher=first, now=AT)
            updated, _ = source(modified=True)
            result = run(tmp, fetch=True, fetcher=updated,
                         now=AT + dt.timedelta(days=1))
            self.assertEqual(result["changed_application_records_review_only"], 6)
            with (Path(tmp) / CHANGED).open(encoding="utf-8-sig") as file:
                changes = list(csv.DictReader(file))
            self.assertEqual(len(changes), 6)
            self.assertTrue(all(
                r["observation"] == "SOURCE_RECORD_CHANGED_NOT_NEW_PUBLICATION"
                for r in changes))
            self.assertTrue((Path(tmp) / STATUS).is_file())

    def test_manual_fetch_is_explicit_and_no_records_from_objectid_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            quiet = run(tmp, fetcher=lambda *args: calls.append(args))
            self.assertEqual(quiet["status"], "FRESH_MANUAL_SOURCE_FETCH_NOT_REQUESTED")
            self.assertEqual(calls, [])

            def objectid_only(url, params):
                number = int(url[len(BASE)+1:].split("/")[0])
                if not url.endswith("/query"):
                    return {"id": number, "name": LAYERS[number].replace("_"," ").title(),
                            "objectIdField": "POLY_ID", "fields": FIELD_LIST}
                if params.get("returnIdsOnly"):
                    return {"objectIds": [10]}
                return {"features": [{"attributes": {
                    "POLY_ID": 10, "DESCRIPTION": "Commercial warehouse"}}]}
            check = run(tmp, fetch=True, fetcher=objectid_only)
            self.assertEqual(check["applications_currently_extracted"], 0)
            self.assertFalse((Path(tmp) / LEDGER).exists())

if __name__ == "__main__":
    unittest.main()
