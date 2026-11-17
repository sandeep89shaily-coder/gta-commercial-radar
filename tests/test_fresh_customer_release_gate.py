"""Offline regression tests for the source-backed fresh customer release."""
import csv
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from gta_fresh_customer_release_gate import (
    run, CLIENT, REVIEW, EVIDENCE_DIR, EARLY, OPEN, WORKLIST, DECISIONS,
    _inventory,
)

DAY = dt.date(2026, 11, 16)
URL = "https://example.org/announcements/123-test-factory"

BODY = (
    "November 16, 2026. New advanced manufacturing factory at "
    "123 Test Road, Toronto. This is an original new factory project, "
    "not a renovation of an old factory. Test Industrial Developments "
    "is the developer and project proponent. Site work planned for "
    "2027. For supplier questions contact projects@testindustrial.example "
    "via the official development office. Procurement status is "
    "unknown; no supplier package or contract award was identified "
    "by the project team's publicly posted update."
)


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def snap(workspace, body=BODY, retrieved="2026-11-16", url=URL):
    folder = workspace / EVIDENCE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    data = {
        "url": url, "retrieved_on": retrieved,
        "text": body, "sha256": hashlib.sha256(body.encode()).hexdigest(),
    }
    (folder / "publisher.json").write_text(json.dumps(data), encoding="utf-8")


def review(candidate, publication_date="2026-11-16"):
    source = lambda quote: {
        "snapshot": "publisher.json", "url": URL, "quote": quote,
    }
    return {
        "record_id": candidate["record_id"], "city": candidate["city"],
        "address": candidate["address"],
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "reviewer": "Independent analyst",
        "reviewed_on": "2026-11-16", "decision": "APPROVE_FOR_EARLY_WARNING",
        "publication": {
            **source("November 16, 2026. New advanced manufacturing factory"),
            "published_on": publication_date,
            "date_basis": "PUBLISHER_DATED_PROJECT_ANNOUNCEMENT",
        },
        "scope_kind": "NEW_PROJECT",
        "scope": source("New advanced manufacturing factory at 123 Test Road, Toronto"),
        "historical_review": {
            "reviewed_by": "Independent analyst", "reviewed_on": "2026-11-16",
            "note": "Compared current publisher announcement with earlier "
                    "project descriptions; no earlier version of this exact "
                    "factory proposal identified in the checked materials.",
        },
        "organization": {
            **source("Test Industrial Developments is the developer and project proponent"),
            "name": "Test Industrial Developments", "role": "DEVELOPER",
        },
        "contact": {
            **source("For supplier questions contact projects@testindustrial.example"),
            "channel": "projects@testindustrial.example",
            "role": "Official development office, not verified purchasing authority",
        },
        "procurement": {
            **source("Procurement status is unknown; no supplier package or contract award"),
            "status": "UNKNOWN_CHECKED", "checked_on": "2026-11-16",
        },
    }


class FreshReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "GTA_RADAR_RESULTS"
        self.root.mkdir()
        self.owner = Path(self.temp.name) / "owner_work"
        self.owner.mkdir()
        save_csv(self.root / CLIENT, [{
            "opportunity_id": "PRIVATE:stable123",
            "city": "Toronto", "address": "123 Test Road, Toronto",
            "project_name": "123 Test Road, Toronto",
            "nature_of_work": "New advanced manufacturing factory",
            "source_url": URL, "application_ids": "26 123456 ABC 01 OZ",
            "source_event_date": "2026-11-16",
            "source_event_date_basis": "APPLICATION_EVENT_NOT_PUBLICATION",
            "stage_gate": "PLANNING_OR_SITE_PLAN_REVIEW",
        }])
        self.candidate = next(iter(_inventory(self.root).values()))
        snap(self.owner)

    def persist(self, case):
        (self.owner / REVIEW).write_text(
            json.dumps({"cases": [case]}), encoding="utf-8")

    def test_without_manual_primary_evidence_nothing_released(self):
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertEqual(result["held_research_candidates"], 1)
        self.assertEqual(result["reviewed_source_matched_early_warnings"], 0)
        self.assertEqual(result["reviewed_open_listings_pending_live_recheck"], 0)
        self.assertIn("NO_PROJECT_SPECIFIC_SOURCE_EVIDENCE_AND_HUMAN_REVIEW",
                      result["hold_reasons"])
        self.assertTrue((self.root / WORKLIST).is_file())
        self.assertEqual(list(csv.DictReader((self.root / EARLY).open(encoding="utf-8-sig"))), [])

    def test_recent_source_matched_human_review_passes_only_early_warning(self):
        self.persist(review(self.candidate))
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertEqual(result["reviewed_source_matched_early_warnings"], 1)
        self.assertEqual(result["reviewed_open_listings_pending_live_recheck"], 0)
        self.assertEqual(result["independently_live_verified_purchasing_buyers"], 0)
        row = list(csv.DictReader((self.root / EARLY).open(encoding="utf-8-sig")))[0]
        self.assertEqual(row["procurement_status"], "UNKNOWN_CHECKED")
        self.assertEqual(row["open_contract_verified_by_radar"], "False")

    def test_old_project_event_cannot_substitute_for_publisher_date(self):
        case = review(self.candidate, publication_date="2026-10-20")
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertEqual(result["reviewed_source_matched_early_warnings"], 0)
        self.assertIn("ORIGINAL_PUBLICATION_NOT_WITHIN_7_DAYS", result["hold_reasons"])

    def test_unsupported_publisher_date_from_retrieval_is_held(self):
        case = review(self.candidate)
        case["publication"]["quote"] = "New advanced manufacturing factory at 123 Test Road"
        case["publication"]["is_retrieval_date"] = True
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertIn("RETRIEVAL_DATE_NOT_PUBLICATION", result["hold_reasons"])
        self.assertIn("PUBLICATION_DATE_NOT_QUOTED_IN_PRIMARY_SOURCE", result["hold_reasons"])

    def test_same_city_unrelated_publisher_is_not_project_evidence(self):
        case = review(self.candidate)
        alt = BODY.replace("123 Test Road, Toronto", "654 Another Road, Toronto")
        snap(self.owner, body=alt)
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertIn("PUBLISHER_SOURCE_DOES_NOT_IDENTIFY_SAME_PROJECT",
                      result["hold_reasons"])

    def test_tampered_snapshot_hash_holds(self):
        case = review(self.candidate)
        path = self.owner / EVIDENCE_DIR / "publisher.json"
        data = json.loads(path.read_text())
        data["text"] += " tampered"
        path.write_text(json.dumps(data))
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertEqual(result["reviewed_source_matched_early_warnings"], 0)
        self.assertIn("SOURCE_SNAPSHOT_HASH_MISMATCH", "|".join(result["hold_reasons"]))

    def test_material_new_scope_without_comparison_holds(self):
        case = review(self.candidate)
        case["scope_kind"] = "MATERIAL_NEW_SCOPE"
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertIn("OLD_AND_NEW_SCOPE_NOT_DISTINGUISHED", result["hold_reasons"])

    def test_open_package_claim_without_a_dated_original_listing_is_held(self):
        case = review(self.candidate)
        case["procurement"].update(
            {"status": "OPEN_PACKAGE_DOCUMENTED", "checked_on": "2026-11-16",
             "package_id": "RFQ-001", "purchaser": "Test Industrial Developments",
             "closing_on": "2026-11-30"})
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertEqual(result["reviewed_source_matched_early_warnings"], 0)
        self.assertIn("OPEN_PACKAGE_NOT_SUPPORTED_BY_LIVE_DATED_SOURCE_TEXT",
                      result["hold_reasons"])

    def test_dated_open_package_is_still_not_independently_live_verified(self):
        case = review(self.candidate)
        line = ("Open tender RFQ-001 for mechanical equipment at 123 Test Road. "
                "Purchaser Test Industrial Developments. Bid closes November 30, 2026.")
        snap(self.owner, body=BODY + " " + line)
        case["procurement"].update(
            {"status": "OPEN_PACKAGE_DOCUMENTED", "checked_on": "2026-11-16",
             "quote": line, "package_id": "RFQ-001",
             "purchaser": "Test Industrial Developments", "closing_on": "2026-11-30"})
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertEqual(result["reviewed_open_listings_pending_live_recheck"], 1)
        self.assertEqual(result["independently_live_verified_open_supplier_contracts"], 0)
        self.assertEqual(len(list(csv.DictReader(
            (self.root / OPEN).open(encoding="utf-8-sig")))), 1)

    def test_stale_source_snapshot_rejected(self):
        case = review(self.candidate)
        snap(self.owner, retrieved="2026-11-12")
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertIn("SOURCE_SNAPSHOT_NOT_CURRENT", "|".join(result["hold_reasons"]))

    def test_mismatched_candidate_fingerprint_rejected(self):
        case = review(self.candidate)
        case["candidate_fingerprint"] = "0" * 64
        self.persist(case)
        result = run(self.root, workspace=self.owner, today=DAY)
        self.assertIn("CANDIDATE_SOURCE_SNAPSHOT_CHANGED", result["hold_reasons"])

    def test_previously_reported_candidate_cannot_be_released_twice(self):
        case = review(self.candidate)
        self.persist(case)
        save_csv(self.owner / "GTA_RADAR_CLIENT_REPORT_HISTORY.csv", [{
            "report_date": "2026-11-15", "report_name": "Already sent",
            "opportunity_id": self.candidate["record_id"],
            "city": self.candidate["city"],
            "address": self.candidate["address"],
        }])
        outcome = run(self.root, workspace=self.owner, today=DAY)
        self.assertEqual(outcome["reviewed_source_matched_early_warnings"], 0)
        self.assertIn("PROJECT_PREVIOUSLY_REPORTED_TO_CLIENT", outcome["hold_reasons"])

    def test_duplicate_review_cases_fail_closed(self):
        case = review(self.candidate)
        (self.owner / REVIEW).write_text(json.dumps({"cases": [case, case]}))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_MISSING"):
            run(self.root, workspace=self.owner, today=DAY)


if __name__ == "__main__":
    unittest.main()
