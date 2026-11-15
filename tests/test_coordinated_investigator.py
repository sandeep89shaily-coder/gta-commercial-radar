"""Acceptance tests: one coordinated investigation, five known problem cases.

Fixtures contain representative public-source snippets, not claims that the
associated permit or buyer was verified in production. No live paid API.
"""
import csv
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from gta_coordinated_investigator import (
    _claim_validation, _request, _validated, investigate,
)

DAY = dt.date(2026, 11, 15)
BIRCHMOUNT = {
    "record_id": "toronto_development_applications:25249692ESC21CD",
    "city": "Toronto", "address": "1430 BIRCHMOUNT RD",
    "application_id": "25249692ESC21CD",
    "project_description":
        "Draft Plan of Condominium, two 3-storey warehouse buildings.",
    "source_url": "https://example.org/official-application",
}
OFFICIAL = {
    "url": "https://example.org/official-application",
    "identity": "EXACT_APPLICATION_ID_IN_FETCHED_TEXT",
    "content": "Application 25249692ESC21CD, 1430 BIRCHMOUNT RD. "
               "Draft Plan of Condominium for two 3-storey warehouse units.",
}
COMPANY = {
    "url": "https://businesspoint.ca/media",
    "identity": "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED",
    "content": "Business Point officially broke ground on their latest "
               "development, Toronto East Business Centre, "
               "located at 1430 Birchmount Rd in Scarborough.",
}
COMPANY_CONTACT = ("Business Point public contact: info@businesspoint.ca")


class CoordinatedInvestigatorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self._csv(BIRCHMOUNT)
        self._dossier(BIRCHMOUNT, [OFFICIAL, COMPANY])

    def _csv(self, *rows):
        path = self.root / "GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(BIRCHMOUNT))
            writer.writeheader()
            writer.writerows(rows)

    def _dossier(self, row, evidence):
        ident = hashlib.sha256(
            (row["record_id"] + ":" + row["city"]).encode()).hexdigest()[:24]
        path = (self.root / "GTA_RADAR_AI_TEN_CAPABILITIES_DOSSIERS"
                / (ident + ".json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**row, "evidence": evidence}),
                        encoding="utf-8")

    def test_birchmount_preflight_finds_company_without_any_spend(self):
        result = investigate(self.root, BIRCHMOUNT["record_id"], today=DAY)
        self.assertEqual(result["status"], "PREFLIGHT_NO_SPEND")
        self.assertEqual(len(result["evidence"]), 2)
        self.assertEqual(
            [x["company"] for x in result["dossier"]["site_company_leads"]],
            ["Business Point"])
        self.assertFalse(result["dossier"]["buyer_verified"])
        self.assertFalse(result["outreach_authorized"])
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_exact_id_missing_fails_before_any_api_call(self):
        with self.assertRaisesRegex(ValueError, "EXACT_CURRENT_TOP10_RECORD_ID_REQUIRED"):
            investigate(self.root, "other:permit", paid=True, today=DAY,
                        token="test", transport=lambda *_:
                        self.fail("Wrong project must never call provider"))

    def test_existing_company_to_contact_to_single_synthesis(self):
        api = []
        def provider(endpoint, payload):
            api.append(endpoint)
            if endpoint == "/chat/completions":
                self.assertEqual(payload["response_format"],
                                 {"type": "json_object"})
                data = json.loads(payload["messages"][1]["content"])
                if "research_stages" in payload["messages"][0]["content"]:
                    answer = {"research_stages": ["buyer_contact_path"],
                              "reason": "Find official business contact"}
                else:
                    self.assertEqual(len(data["evidence"]), 3)
                    answer = {
                        "classification": "HOLD",
                        "commercial_reason":
                            "Development confirmed; purchasing unknown",
                        "disqualification_reason":
                            "Construction may have started",
                        "procurement_status": "UNKNOWN",
                        "next_verification":
                            "Obtain applicant and current construction status",
                        "potential_trades": [],
                        "claims": [
                            {"kind": "company", "subject": "Business Point",
                             "relationship": "Site-level developer context",
                             "source_index": 1,
                             "quote": COMPANY["content"]},
                            {"kind": "contact", "subject": "Business Point",
                             "relationship": "Public corporate route only",
                             "source_index": 2, "quote": COMPANY_CONTACT},
                        ],
                    }
                return {"choices": [{"finish_reason": "stop", "message": {
                    "content": json.dumps(answer)}}],
                    "usage": {"prompt_tokens": 500,
                              "completion_tokens": 130}}
            if endpoint == "/v1/tools/search":
                self.assertIn("Business Point", payload["query"])
                return {"results": [{"url": "https://businesspoint.ca/contact",
                                     "snippet": "Business Point contact"}]}
            if endpoint == "/v1/tools/fetch":
                return {"content": COMPANY_CONTACT}
            self.fail(endpoint)
        result = investigate(self.root, BIRCHMOUNT["record_id"], paid=True,
                             token="test", today=DAY, transport=provider)
        self.assertEqual(result["status"], "SOURCE_BACKED_REVIEW_COMPLETE")
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(api, ["/chat/completions", "/v1/tools/search",
                               "/v1/tools/fetch", "/chat/completions"])
        self.assertEqual(len(result["accepted_claims"]), 2)
        self.assertTrue(any("info@businesspoint.ca" in x["content"]
                            for x in result["evidence"]))
        self.assertFalse(result["outreach_authorized"])
        self.assertFalse(result["dossier"]["buyer_verified"])
        self.assertEqual(result["analysis"]["procurement_status"], "UNKNOWN")
        again = investigate(self.root, BIRCHMOUNT["record_id"], paid=True,
                            token="test", today=DAY, transport=lambda *_:
                            self.fail("No repeat paid call"))
        self.assertTrue(again["checkpoint_reused"])

    def test_coordinated_report_joins_canonical_top10_by_exact_identity(self):
        from gta_commercial_qualification_review import build
        # One realistic municipal source record, then the coordinated
        # overlay; do not let a model claim turn into a buyer.
        pending = self.root / "GTA_RADAR_V8_PENDING_QUEUE.csv"
        with pending.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "project_id", "city", "address", "source_keys",
                "description", "record_source_url", "current_source_status"])
            writer.writeheader()
            writer.writerow({
                "project_id": BIRCHMOUNT["record_id"],
                "city": BIRCHMOUNT["city"],
                "address": BIRCHMOUNT["address"],
                "source_keys": BIRCHMOUNT["application_id"],
                "description": BIRCHMOUNT["project_description"],
                "record_source_url": BIRCHMOUNT["source_url"],
                "current_source_status": "Under Review"})
        overlay = {
            "projects": {BIRCHMOUNT["record_id"]: {
                **BIRCHMOUNT,
                "status": "SOURCE_BACKED_REVIEW_COMPLETE",
                "company_site_leads": [{
                    "company": "Business Point",
                    "association": "GROUNDBREAKING_SITE_ASSOCIATION",
                    "source_url": COMPANY["url"]}],
                "source_backed_claims": [],
                "ai_commercial_classification_unverified": "HOLD",
                "source_count": 2,
                "report_path": "example.json",
                "verified_buyer": False,
                "outreach_authorized": False}}}
        (self.root / "GTA_RADAR_COORDINATED_PROJECT_OVERLAY.json").write_text(
            json.dumps(overlay), encoding="utf-8")
        result = build(self.root, today=DAY, apply_ai=False)
        self.assertEqual(result["coordinated_projects_integrated"], 1)
        selected = next(x for x in result["all_candidates"]
                        if x["record_id"] == BIRCHMOUNT["record_id"])
        self.assertEqual(selected["coordinated_company_leads"][0]["company"],
                         "Business Point")
        self.assertEqual(selected["coordinated_assessment_unverified"],
                         "HOLD")
        self.assertFalse(selected.get("buyer_verified", False))

    def test_five_failure_cases_require_correct_independent_evidence(self):
        rows = [
            BIRCHMOUNT,
            {"record_id": "toronto:keele", "city": "Toronto",
             "address": "611 KEELE ST", "application_id": "21170364S4505TLAB",
             "project_description": "Historical self-storage proposal",
             "source_url": "https://example.org/keele"},
            {"record_id": "brampton:advance", "city": "Brampton",
             "address": "75 ADVANCE BLVD", "application_id": "26-073967-P01-01",
             "project_description": "Alteration", "source_url": "https://example.org/a"},
            {"record_id": "brampton:hwy50", "city": "Brampton",
             "address": "8380 HIGHWAY 50", "application_id": "26-182678-000-00",
             "project_description": "Industrial alteration",
             "source_url": "https://example.org/b"},
            {"record_id": "brampton:glidden", "city": "Brampton",
             "address": "238 GLIDDEN RD", "application_id": "26-185633-000-00",
             "project_description": "Industrial work",
             "source_url": "https://example.org/c"},
        ]
        self._csv(*rows)
        self._dossier(rows[1], [
            {"url": "https://example.org/keele",
             "content": "611 KEELE ST original self-storage proposed, "
                        "later proposal replaced it with mixed-use residential."}
        ])
        self._dossier(rows[2], [
            {"url": "https://example.org/wrong",
             "content": "175 ADVANCE BLVD has another company."}
        ])
        self._dossier(rows[3], [
            {"url": "https://example.org/hwy",
             "content": "8380 HIGHWAY 50 industrial alteration permit "
                        "26-182678-000-00."}
        ])
        self._dossier(rows[4], [
            {"url": "https://example.org/glidden",
             "content": "238 GLIDDEN RD — industrial property. "
                        "No confirmed permit buyer listed."}
        ])
        evidence_counts = []
        for row in rows:
            result = investigate(self.root, row["record_id"], today=DAY)
            self.assertEqual(result["status"], "PREFLIGHT_NO_SPEND")
            self.assertFalse(result["outreach_authorized"])
            self.assertFalse(result["dossier"]["buyer_verified"])
            self.assertEqual(result["dossier"]["procurement_status"],
                             "UNKNOWN")
            evidence_counts.append(len(result["evidence"]))
        self.assertEqual(evidence_counts, [2, 1, 0, 1, 1])
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_unsupported_company_and_open_bid_claims_rejected(self):
        sources = _validated([OFFICIAL, COMPANY], BIRCHMOUNT)
        bad = {"claims": [
            {"kind": "company", "subject": "Invented LLC",
             "source_index": 1,
             "quote": COMPANY["content"]},
            {"kind": "procurement", "subject": "Open contract",
             "source_index": 0, "quote": "Open unawarded tender"},
        ]}
        self.assertEqual(_claim_validation(bad, sources), [])

    def test_full_serialized_model_inputs_and_finite_plan(self):
        payload = _request(BIRCHMOUNT, _validated(
            [OFFICIAL, COMPANY], BIRCHMOUNT),
            "HVAC Southern Ontario", "synthesis")
        parsed = json.loads(payload["messages"][1]["content"])
        self.assertEqual(parsed["project"]["record_id"],
                         BIRCHMOUNT["record_id"])
        self.assertEqual(len(parsed["evidence"]), 2)
        self.assertEqual(payload["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
