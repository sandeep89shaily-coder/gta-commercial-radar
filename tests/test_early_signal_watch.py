"""Offline tests: no live municipalities, DeepSeek, scheduler or V8 database."""
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import early_signal_watch as early


class FakeReply:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, records, fail=False):
        self.records = records
        self.fail = fail
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        if self.fail:
            raise early.requests.RequestException("network unavailable")
        params = params or {}
        if params.get("returnIdsOnly") == "true":
            return FakeReply({"objectIds": [r["OBJECTID"] for r in self.records]})
        if params.get("objectIds"):
            ids = set(map(int, params["objectIds"].split(",")))
            return FakeReply({"features": [
                {"attributes": r} for r in self.records if r["OBJECTID"] in ids
            ]})
        return FakeReply({"objectIdField": "OBJECTID", "fields": [
            {"name": "OBJECTID"}, {"name": "APPLICATION_NUMBER"}
        ]})


def sample(description="Industrial warehouse expansion"):
    return {"OBJECTID": 101, "APPLICATION_NUMBER": "SPA-123",
            "FOLDERDESCRIPTION": description, "FULL_ADDRESS": "22 Test Rd",
            "STATUS_DESC": "Submitted", "SUBMIT_DATE": 1792000000000}


class EarlySignalTests(unittest.TestCase):
    def test_baseline_then_change(self):
        with tempfile.TemporaryDirectory() as root:
            src = ["toronto_development"]
            out = Path(root) / "outputs"
            self.assertEqual(early.run(root, out, src,
                FakeSession([sample()]), "2026-10-24T10:00:00+00:00"), 0)
            with (out / "EARLY_SIGNALS_CHANGES_REVIEW_ONLY.csv").open(
                    encoding="utf-8-sig", newline="") as f:
                self.assertEqual(list(csv.DictReader(f)), [])
            self.assertEqual(early.run(root, out, src,
                FakeSession([sample()]), "2026-10-25T10:00:00+00:00"), 0)
            self.assertEqual(early.run(root, out, src,
                FakeSession([sample("Industrial warehouse expansion and cold storage")]),
                "2026-10-26T10:00:00+00:00"), 0)
            with (out / "EARLY_SIGNALS_CHANGES_REVIEW_ONLY.csv").open(
                    encoding="utf-8-sig", newline="") as f:
                records = list(csv.DictReader(f))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["change_type"], "UPDATED")
            self.assertEqual(records[0]["record_scope"], "APPLICATION_ID")
            self.assertEqual(records[0]["commercial_signal"], "POSSIBLE_COMMERCIAL")
            self.assertEqual(records[0]["qualification"], "PUBLIC_PLANNING_RECORD_REVIEW_ONLY")

    def test_upgrade_legacy_database_preserves_first_seen_and_no_false_update(self):
        with tempfile.TemporaryDirectory() as root:
            src = ["toronto_development"]
            stamp = "2026-10-24T10:00:00+00:00"
            self.assertEqual(early.run(root, None, src, FakeSession([sample()]), stamp), 0)
            database = Path(root)/"early_signals_review.sqlite"
            db = sqlite3.connect(database)
            try:
                row = db.execute("SELECT record_key, content FROM observations").fetchone()
                old = json.loads(row[1])
                old.pop("quality_version", None)
                old.pop("source_date_basis", None)
                old.pop("company_role", None)
                old["source_application_date"] = ""
                old["commercial_signal"] = "USE_UNKNOWN"
                old["description"] = sample()["FOLDERDESCRIPTION"]
                import hashlib
                payload = json.dumps(old, ensure_ascii=False, sort_keys=True)
                hashed = hashlib.sha256(json.dumps(
                    {k:v for k,v in old.items() if k != "observed_at"},
                    sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                db.execute("UPDATE observations SET digest=?,content=?",
                           (hashed, payload))
                db.commit()
            finally:
                db.close()
            self.assertEqual(early.run(root, None, src, FakeSession([sample()]),
                                       "2026-10-25T10:00:00+00:00"), 0)
            db = sqlite3.connect(database)
            try:
                row = db.execute("SELECT first_seen,content FROM observations").fetchone()
                self.assertEqual(row[0], stamp)
                upgraded = json.loads(row[1])
                self.assertEqual(upgraded["quality_version"], 3)
                self.assertTrue(upgraded["source_application_date"].startswith("2026-"))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            finally:
                db.close()

    def test_duplicate_applications_fall_back_to_feature_identity(self):
        source = next(s for s in early.SOURCES if s["id"] == "toronto_development")
        one = sample()
        two = {**sample(), "OBJECTID": 102, "FULL_ADDRESS": "24 Test Rd"}
        rows = early.prepare_rows(source, [one, two], "OBJECTID", "2026-10-24")
        self.assertEqual({r["record_key"] for r in rows}, {"OID:101", "OID:102"})
        self.assertTrue(all(r["record_scope"] == "FEATURE_ONLY" for r in rows))

    def test_york_source_reference_and_municipality_preserved(self):
        source = next(s for s in early.SOURCES if s["id"] == "york_region_development")
        row = {"OBJECTID": 11, "APPL_GISID": "53", "MUN_NAME": "Vaughan",
               "REG_FILE_NUM": "19T-V-123", "ADDRESS": "100 Test Road",
               "APPL_DESC": "Industrial warehouse", "DATE_RECVD": None,
               "SUBMISSION_DATE__C": 1792000000000}
        record = early.prepare_rows(source, [row], "OBJECTID", "2026-10-24")[0]
        self.assertEqual(record["city"], "Vaughan")
        self.assertEqual(record["municipal_reference"], "19T-V-123")
        self.assertEqual(record["source_date_basis"], "SUBMISSION_DATE__C")
        self.assertEqual(record["company_role"], "COMPANY_UNKNOWN")
        self.assertEqual(record["quality_version"], 3)

    def test_failed_fetch_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            src = ["toronto_development"]
            self.assertEqual(early.run(root, None, src, FakeSession([sample()]),
                                       "2026-10-24T10:00:00+00:00"), 0)
            self.assertEqual(early.run(root, None, src, FakeSession([], fail=True),
                                       "2026-10-25T10:00:00+00:00"), 1)
            db = sqlite3.connect(Path(root) / "early_signals_review.sqlite")
            try:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1)
            finally:
                db.close()

    def test_oversized_get_request_retries_small_batches(self):
        class RejectLargeRequests(FakeSession):
            def get(self, url, params=None, timeout=None):
                if params and params.get("objectIds"):
                    ids = params["objectIds"].split(",")
                    if len(ids) > 20:
                        raise early.requests.HTTPError("404 batch request rejected")
                return super().get(url, params=params, timeout=timeout)

        with tempfile.TemporaryDirectory() as root:
            rows = [
                {**sample(), "OBJECTID": i, "APPLICATION_NUMBER": f"SPA-{i}"}
                for i in range(101, 172)
            ]
            result = early.run(root, None, ["toronto_development"],
                               RejectLargeRequests(rows), "2026-10-24T10:00:00+00:00")
            self.assertEqual(result, 0)
            db = sqlite3.connect(Path(root) / "early_signals_review.sqlite")
            try:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
                                 len(rows))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            finally:
                db.close()

    def test_nonjson_response_reports_request_stage(self):
        class NotJson:
            headers = {"content-type": "text/html"}
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                raise ValueError("HTML, not JSON")

        class BadMetadata(FakeSession):
            def get(self, url, params=None, timeout=None):
                return NotJson()

        with self.assertRaisesRegex(RuntimeError, "toronto_development metadata"):
            early.fetch_layer(BadMetadata([sample()]),
                              next(s for s in early.SOURCES if s["id"] == "toronto_development"))

    def test_empty_and_duplicate_id_batches_refused(self):
        source = early.SOURCES[0]
        with self.assertRaises(RuntimeError):
            early.fetch_layer(FakeSession([]), source)
        duplicated = [sample(), sample()]
        with self.assertRaises(RuntimeError):
            early.fetch_layer(FakeSession(duplicated), source)


if __name__ == "__main__":
    unittest.main()
