"""Regression tests for source-specific project/company/site mention graph."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from gta_project_company_evidence_graph import build, run, OUTPUT


EVENT_FIELDS = [
    "event_id", "project_id", "city", "site_id", "source_family",
    "source_id", "source_record_id", "organization", "organization_role",
    "source_url",
]
HINT_FIELDS = [
    "event_id", "project_id", "role_type_claimed",
    "organization_name_claimed", "official_record_url_reference",
    "role_document_quote_present",
]
OFFICIAL_FIELDS = [
    "city", "import_project_id", "application_id", "import_source_url",
    "applicant_unverified", "property_owner_unverified",
    "planning_reviewer_unverified",
]


class CompanyGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "FACILITY_INTELLIGENCE_PILOT").mkdir()
        (self.root / "FACILITY_DOSSIER_PILOT").mkdir()

    def csv(self, filename, fields, rows):
        path = self.root / filename
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def events(self, rows):
        self.csv("FACILITY_INTELLIGENCE_PILOT/GTA_RADAR_FACILITY_EVIDENCE_EVENTS.csv",
                 EVENT_FIELDS, rows)

    def hints(self, rows):
        self.csv("FACILITY_DOSSIER_PILOT/GTA_RADAR_EXACT_PROJECT_ROLE_HINTS_TO_VERIFY.csv",
                 HINT_FIELDS, rows)

    def officials(self, rows):
        self.csv("FACILITY_DOSSIER_PILOT/GTA_RADAR_OFFICIAL_APPLICATION_EXACT_SITE_ROLE_REVIEW.csv",
                 OFFICIAL_FIELDS, rows)

    def test_missing_inputs_remain_missing_and_not_verified(self):
        report = build(self.root)
        self.assertEqual(report["project_candidates"], 0)
        self.assertEqual(report["source_statuses"]["facility_events"], "MISSING")
        self.assertEqual(report["source_statuses"]["council_application_reconciliation"], "MISSING")
        self.assertEqual(report["verified_buyers"], 0)

    def test_exact_event_project_link_and_role_are_unverified(self):
        self.events([{
            "event_id": "E1", "project_id": "TOR:001", "city": "Toronto",
            "site_id": "S1", "source_family": "radar",
            "source_id": "toronto_development_applications",
            "source_record_id": "001", "organization": "",
            "organization_role": "UNKNOWN", "source_url": "https://toronto.ca/app",
        }])
        self.hints([{
            "event_id": "E1", "project_id": "TOR:001",
            "role_type_claimed": "OWNER_CLAIM",
            "organization_name_claimed": "Example Holdings Ltd",
            "official_record_url_reference": "https://toronto.ca/record",
            "role_document_quote_present": "NO",
        }])
        report = run(self.root)
        self.assertEqual(report["project_candidates"], 1)
        self.assertEqual(report["organization_mentions"], 1)
        self.assertEqual(report["claimed_relationships"], 1)
        self.assertEqual(report["edges"][0]["role_claimed"], "PROPERTY_OWNER")
        self.assertFalse(report["edges"][0]["project_role_verified"])
        self.assertFalse(report["edges"][0]["buyer_verified"])
        self.assertEqual(report["verified_project_company_roles"], 0)
        self.assertTrue((self.root / OUTPUT).is_file())

    def test_unmatched_role_hint_cannot_create_project_or_company(self):
        self.events([{
            "event_id": "E1", "project_id": "PROJECT-A", "city": "Toronto",
            "site_id": "S1", "source_family": "radar",
            "source_id": "Toronto", "source_record_id": "A",
            "organization": "", "organization_role": "UNKNOWN", "source_url": "",
        }])
        self.hints([{"event_id": "E1", "project_id": "DIFFERENT-PROJECT",
                     "role_type_claimed": "BUYER_CLAIM",
                     "organization_name_claimed": "Fake Buyer Inc"}])
        report = build(self.root)
        self.assertEqual(report["project_candidates"], 0)
        self.assertEqual(report["organization_mentions"], 0)
        self.assertEqual(report["holds"][0]["reason"],
                         "ROLE_HINT_EVENT_OR_PROJECT_ID_MISMATCH")

    def test_same_company_string_not_global_company_entity_across_cities(self):
        self.officials([
            {"city": "Vaughan", "import_project_id": "APP-1",
             "application_id": "R01/26", "import_source_url": "https://vaughan.ca/app",
             "property_owner_unverified": "Example Holdings Ltd"},
            {"city": "Kitchener", "import_project_id": "APP-1",
             "application_id": "R01/26", "import_source_url": "https://kitchener.ca/app",
             "property_owner_unverified": "Example Holdings Ltd"},
        ])
        report = build(self.root)
        self.assertEqual(report["project_candidates"], 2)
        self.assertEqual(report["organization_mentions"], 2)
        self.assertEqual(report["claimed_relationships"], 2)
        self.assertEqual(report["verified_company_entities"], 0)
        self.assertEqual(len({x["node_id"] for x in report["organization_nodes"]}), 2)
        self.assertTrue(all(x["canonical_company_id"] is None
                            for x in report["organization_nodes"]))

    def test_same_site_organization_is_not_a_project_role(self):
        self.events([{
            "event_id": "E2", "project_id": "P1", "city": "Brampton",
            "site_id": "SITE42", "source_family": "industrial",
            "source_id": "ero", "source_record_id": "019-1234",
            "organization": "Example Manufacturing",
            "organization_role": "REGULATORY_PROPONENT_NOT_VERIFIED_BUYER",
            "source_url": "https://ero.ontario.ca/notice/019-1234",
        }])
        report = build(self.root)
        self.assertEqual(report["project_candidates"], 0)
        self.assertEqual(report["source_site_contexts"], 1)
        self.assertEqual(report["edges"][0]["relationship"],
                         "SOURCE_SITE_ORGANIZATION_MENTION_NOT_PROJECT_ROLE")
        self.assertTrue(report["edges"][0]["from_node"].startswith("site:"))
        self.assertEqual(report["verified_buyers"], 0)

    def test_conflicting_source_claims_are_review_holds(self):
        self.events([{
            "event_id": "E1", "project_id": "APP-1", "city": "Vaughan",
            "site_id": "", "source_family": "radar",
            "source_id": "city", "source_record_id": "App/1",
            "organization": "", "organization_role": "UNKNOWN", "source_url": "",
        }])
        self.hints([{
            "event_id": "E1", "project_id": "APP-1",
            "role_type_claimed": "OWNER_CLAIM",
            "organization_name_claimed": "First Company",
        }])
        self.officials([{
            "city": "Vaughan", "import_project_id": "APP-1",
            "application_id": "R01/26", "import_source_url": "https://vaughan.ca/",
            "property_owner_unverified": "Second Company",
        }])
        report = build(self.root)
        self.assertEqual(report["role_conflicts"], 1)
        self.assertEqual(report["conflicts"][0]["status"],
                         "CONFLICTING_SOURCE_ROLE_NAMES_HUMAN_REVIEW_REQUIRED")
        self.assertEqual(report["verified_project_company_roles"], 0)

    def test_council_exact_id_context_is_not_company_role(self):
        (self.root / "GTA_RADAR_CROSS_SOURCE_RECONCILIATION.json").write_text(
            json.dumps({
                "status": "READ_ONLY_CROSS_SOURCE_REVIEW",
                "review_candidates": [{
                    "status": "EXACT_ID_CANDIDATE_HUMAN_REVIEW_REQUIRED",
                    "project_id": "TOR-A", "city": "Toronto",
                    "application_id": "D23ZZZ22.012",
                    "source_url": "https://toronto.ca/report",
                    "evidence_id": "a1", "source_sha256": "b"*64,
                    "page": 4, "start_ms": None,
                }]
            }), encoding="utf-8")
        report = build(self.root)
        self.assertEqual(report["council_id_context_links"], 1)
        self.assertEqual(report["claimed_relationships"], 0)
        self.assertEqual(report["council_evidence"][0]["pdf_page"], 4)
        self.assertFalse(report["council_evidence"][0]["project_link_verified"])

    def test_unrecognized_schema_rejected_and_good_output_preserved(self):
        run(self.root)
        previous = (self.root / OUTPUT).read_bytes()
        path = self.root / "FACILITY_DOSSIER_PILOT/GTA_RADAR_EXACT_PROJECT_ROLE_HINTS_TO_VERIFY.csv"
        path.write_text("unexpected,fields\n1,2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SCHEMA_MISMATCH"):
            run(self.root)
        self.assertEqual((self.root / OUTPUT).read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
