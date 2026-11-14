"""Offline deterministic regression tests for source-backed review/award gating."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_supplier_verification_gate import build, run, GRAPH, INPUT, REPORT, \
    ROLE_QUEUE, TENDER_QUEUE

NOW = dt.datetime(2026, 11, 14, 17, 0, tzinfo=dt.timezone.utc)
EDGE = "edge:abc0123"
PROJECT = "project:xyz456"
ORG = "org_mention:m1"
HASH = "a" * 64


class ProcurementGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.results = self.workspace / "GTA_RADAR_RESULTS"
        self.results.mkdir()
        self.graph()

    def graph(self):
        graph = {
            "status": "PROJECT_COMPANY_MENTION_GRAPH_REVIEW_ONLY",
            "project_nodes": [{"node_id": PROJECT, "project_id": "BURL:2026-12",
                               "city": "Burlington", "identity_verified": False}],
            "organization_nodes": [{"node_id": ORG,
                                    "organization_name_as_stated": "Example Industrial Ltd",
                                    "identity_verified": False}],
            "edges": [{"edge_id": EDGE, "from_node": PROJECT, "to_node": ORG,
                       "relationship": "PROJECT_ROLE_SOURCE_CLAIM",
                       "role_claimed": "DEVELOPER",
                       "source_url": "https://burlington.ca/source",
                       "source_event_id": "event-123",
                       "source_record_id": "2026-12",
                       "project_role_verified": False,
                       "buyer_verified": False}]
        }
        (self.results / GRAPH).write_text(json.dumps(graph), encoding="utf-8")

    def role(self, **overrides):
        row = {
            "edge_id": EDGE, "project_node_id": PROJECT, "role": "DEVELOPER",
            "organization_name": "Example Industrial Ltd",
            "decision": "CONFIRM_ROLE", "reviewer_id": "analyst-1",
            "reviewed_at_utc": "2026-11-14T16:00:00Z",
            "evidence_url": "https://burlington.ca/2026-12",
            "evidence_quote": "Example Industrial Ltd is the proposed developer for this property",
            "evidence_locator": "Application page 4",
            "source_document_sha256": HASH
        }
        return {**row, **overrides}

    def tender(self, **overrides):
        row = {
            "project_node_id": PROJECT, "tender_id": "RFP-2026-998",
            "decision": "OPEN_PUBLIC_TENDER", "sector": "HVAC",
            "work_scope": "Central chilled water equipment supply",
            "reviewer_id": "analyst-1",
            "reviewed_at_utc": "2026-11-14T16:00:00Z",
            "tender_url": "https://burlington.ca/rfp/998",
            "evidence_quote": "Request for tenders for central chilled water equipment supply",
            "source_document_sha256": HASH,
            "closing_date": "2026-11-23",
            "buyer_role_edge_id": EDGE,
            "authority_evidence_url": "https://burlington.ca/rfp/998",
            "authority_evidence_quote": "Submissions shall be made to Example Industrial Ltd",
        }
        return {**row, **overrides}

    def decisions(self, roles=None, tenders=None):
        (self.workspace / INPUT).write_text(json.dumps({
            "version": 1, "role_reviews": roles or [],
            "procurement_reviews": tenders or [],
        }), encoding="utf-8")

    def test_without_review_manifest_produces_real_queue_not_buyer_claim(self):
        result = run(self.results, self.workspace)
        self.assertEqual(result["source_graph_role_claims"], 1)
        self.assertEqual(result["status"],
                         "NO_OPERATOR_VERIFICATION_MANIFEST_REVIEW_QUEUE_ONLY")
        self.assertEqual(result["reviewer_attested_role_claims"], 0)
        self.assertEqual(result["verified_buyers"], 0)
        self.assertEqual(result["verified_open_supplier_contracts"], 0)
        self.assertTrue((self.results / ROLE_QUEUE).exists())
        self.assertTrue((self.results / REPORT).exists())
        with (self.results / ROLE_QUEUE).open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["organization_name"], "Example Industrial Ltd")

    def test_matching_role_human_attestation_remains_not_independent(self):
        self.decisions(roles=[self.role()])
        outcome = build(self.results, self.workspace, now=NOW)
        self.assertEqual(outcome["reviewer_attested_role_claims"], 1)
        accepted = outcome["accepted_roles"][0]
        self.assertFalse(accepted["buyer_verified"])
        self.assertFalse(accepted["legal_identity_verified"])
        self.assertEqual(outcome["verified_buyers"], 0)
        self.assertEqual(outcome["verified_open_supplier_contracts"], 0)

    def test_duplicate_conflicting_role_cannot_leave_accepted_approval(self):
        self.decisions(roles=[
            self.role(decision="CONFIRM_ROLE"),
            self.role(decision="REJECT_ROLE"),
        ], tenders=[self.tender()])
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["reviewer_attested_role_claims"], 0)
        self.assertEqual(result["reviewer_rejected_role_claims"], 0)
        self.assertEqual(result["tender_reviews"][0]["review_status"],
                         "PURCHASING_AUTHORITY_NOT_REVIEWED_HOLD")
        self.assertEqual(result["role_queue"][0]["review_status"],
                         "ROLE_REVIEW_HELD_OR_CONFLICTING")

    def test_unreviewed_projects_receive_procurement_tasks_not_fake_tenders(self):
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["projects_queued_for_procurement_research"], 1)
        task = result["tender_queue"][0]
        self.assertEqual(task["supplier_sector"], "UNDETERMINED")
        self.assertEqual(task["review_status"],
                         "NO_PROJECT_SPECIFIC_PROCUREMENT_EVIDENCE")
        self.assertEqual(task["tender_id"], "")
        self.assertEqual(result["verified_open_supplier_contracts"], 0)

    def test_reject_role_is_reflected_in_queue_without_buyers(self):
        self.decisions(roles=[self.role(decision="REJECT_ROLE")])
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["reviewer_attested_role_claims"], 0)
        self.assertEqual(result["reviewer_rejected_role_claims"], 1)
        self.assertEqual(result["role_queue"][0]["review_status"],
                         "ROLE_REJECTED_BY_HUMAN_REVIEW")

    def test_wrong_name_or_edge_does_not_accept_role(self):
        self.decisions(roles=[
            self.role(organization_name="Other Company", edge_id=EDGE)
        ])
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["reviewer_attested_role_claims"], 0)
        self.assertEqual(result["held_or_conflicting_decisions"], 1)
        self.decisions(roles=[self.role(edge_id="edge:unknown")])
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["reviewer_attested_role_claims"], 0)

    def test_bad_timestamp_quote_and_source_are_held(self):
        for modified in (
            {"reviewed_at_utc": "2026-10-01T12:00:00Z"},
            {"reviewed_at_utc": "2026-12-01T12:00:00Z"},
            {"reviewed_at_utc": "2026-11-14T16:00:00"},
            {"evidence_url": "http://localhost/doc"},
            {"evidence_quote": "An unrelated project in this city was approved."},
            {"source_document_sha256": "not-a-hash"},
            {"evidence_locator": ""},
        ):
            self.decisions(roles=[self.role(**modified)])
            result = build(self.results, self.workspace, now=NOW)
            self.assertEqual(result["reviewer_attested_role_claims"], 0, modified)
            self.assertEqual(result["held_or_conflicting_decisions"], 1, modified)

    def test_open_public_tender_holds_when_buyer_unreviewed(self):
        self.decisions(tenders=[self.tender()])
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["tender_reviews"][0]["review_status"],
                         "PURCHASING_AUTHORITY_NOT_REVIEWED_HOLD")
        self.assertEqual(result["verified_open_supplier_contracts"], 0)

    def test_open_tender_requires_live_recheck_even_when_roles_reviewed(self):
        self.decisions(roles=[self.role()], tenders=[self.tender()])
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["reviewer_attested_open_tender_needing_live_recheck"], 1)
        self.assertFalse(result["tender_reviews"][0]["procurement_live_verified"])
        self.assertFalse(result["tender_reviews"][0]["outreach_authorized"])
        self.assertEqual(result["verified_open_supplier_contracts"], 0)
        self.assertEqual(result["tender_queue"][0]["supplier_sector"], "HVAC")

    def test_expired_future_far_and_awarded_tenders_are_not_open(self):
        for fields, status in (
            ({"closing_date": "2026-11-13"}, "CLOSING_DATE_PASSED_HOLD"),
            ({"closing_date": "2030-01-01"}, "IMPLAUSIBLE_CLOSING_DATE_HOLD"),
            ({"decision": "AWARDED"}, "REVIEWED_TENDER_CLOSED_OR_AWARDED"),
            ({"decision": "CLOSED"}, "REVIEWED_TENDER_CLOSED_OR_AWARDED"),
        ):
            self.decisions(roles=[self.role()], tenders=[self.tender(**fields)])
            result = build(self.results, self.workspace, now=NOW)
            self.assertEqual(result["tender_reviews"][0]["review_status"], status)
            self.assertEqual(result["reviewer_attested_open_tender_needing_live_recheck"], 0)

    def test_duplicate_tender_decisions_conflict_and_block(self):
        self.decisions(roles=[self.role()], tenders=[
            self.tender(), self.tender(decision="AWARDED")
        ])
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["tender_reviews"], [])
        self.assertEqual(result["reviewer_attested_open_tender_needing_live_recheck"], 0)
        self.assertEqual(result["held_or_conflicting_decisions"], 1)

    def test_failed_input_does_not_overwrite_previous_report(self):
        run(self.results, self.workspace)
        original = (self.results / REPORT).read_bytes()
        (self.workspace / INPUT).write_text('{"version": 9}')
        with self.assertRaisesRegex(ValueError, "SCHEMA_OR_SIZE"):
            run(self.results, self.workspace)
        self.assertEqual((self.results / REPORT).read_bytes(), original)

    def test_cross_project_buyer_reference_does_not_gate_tender(self):
        self.decisions(roles=[self.role()],
                       tenders=[self.tender(project_node_id="project:unrelated")])
        result = build(self.results, self.workspace, now=NOW)
        self.assertEqual(result["tender_reviews"], [])
        self.assertEqual(result["verified_buyers"], 0)

    def test_csv_formula_injection_is_escaped(self):
        graph = json.loads((self.results / GRAPH).read_text())
        graph["organization_nodes"][0]["organization_name_as_stated"] = "=HYPERLINK('evil')"
        (self.results / GRAPH).write_text(json.dumps(graph))
        run(self.results, self.workspace)
        with (self.results / ROLE_QUEUE).open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(rows[0]["organization_name"].startswith("'="))


if __name__ == "__main__":
    unittest.main()
