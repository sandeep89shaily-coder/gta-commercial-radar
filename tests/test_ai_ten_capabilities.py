"""Offline acceptance of all ten capabilities, evidence gating, checkpointing."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_ai_ten_capabilities import STAGES, run, _evidence, _verified_claims
from gta_commercial_qualification_review import build as qualification_build
from gta_ai_ten_source_enrichment import enrich as source_enrich
import v5_investigator as v5

TODAY = dt.date(2026, 11, 15)
SOURCE_QUOTE = ("The previous proposal for a self-storage facility was "
                "replaced by a residential mixed-use development.")


class TenCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = {
            "record_id": "test:permit:2021", "city": "Toronto",
            "address": "611 Keele St, Toronto, ON",
            "application_id": "21170364S4505TLAB",
            "project_description": "Self-storage facility",
            "source_url": "https://example.org/permit"}
        with (self.root / "GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv").open(
                "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.record))
            writer.writeheader()
            writer.writerow(self.record)
        self.probe = self.root / (
            "GTA_RADAR_TOP10_DEEPSEEK_COMPANY_PROBE_2026-11-15_FROM_1_COUNT_1.json")
        self.probe.write_text(json.dumps({
            "reviews": [{
                "record_id": self.record["record_id"],
                "city": "Toronto", "model_summary_research_hint_not_verified":
                    "This assertion must NOT be treated as independent evidence",
                "independently_fetched_context": [
                    {"url": "https://example.org/independent-report",
                     "identity": "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED",
                     "excerpt": "611 Keele St, Toronto, ON. " + SOURCE_QUOTE,
                     "role_excerpt": "",
                     "retrieved_on": "2026-11-15"}
                ]}]}), encoding="utf-8")

    def test_exact_record_id_preflight_selects_correct_project(self):
        with (self.root / "GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv").open(
                "a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.record))
            writer.writerow({**self.record,
                             "record_id": "toronto:other",
                             "address": "1430 Birchmount Road"})
        selected = run(self.root, record_id="toronto:other", today=TODAY)
        self.assertEqual(selected["projects_selected"], 1)
        self.assertEqual(selected["results"][0]["record_id"], "toronto:other")
        self.assertEqual(selected["results"][0]["address"],
                         "1430 Birchmount Road")
        self.assertEqual(selected["status"], "PREFLIGHT_NO_SPEND")
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_exact_record_id_must_exist_and_must_not_conflict_with_index(self):
        with self.assertRaisesRegex(ValueError, "EXACT_RECORD_ID_NOT_IN_CURRENT_TOP10"):
            run(self.root, record_id="missing", today=TODAY, paid=True,
                token="test", transport=lambda *_:
                    self.fail("No paid call on wrong selected project"))
        with self.assertRaisesRegex(ValueError,
                                    "EXACT_RECORD_ID_CANNOT_COMBINE_WITH_START_INDEX"):
            run(self.root, record_id=self.record["record_id"],
                start_index=1, today=TODAY, paid=True, token="test",
                transport=lambda *_: self.fail("No paid call"))

    def test_preflight_is_free_and_exposes_ten_stages(self):
        result = run(self.root, today=TODAY)
        self.assertEqual(result["status"], "PREFLIGHT_NO_SPEND")
        self.assertEqual(len(STAGES), 10)
        self.assertEqual(result["results"][0]["available_source_count"], 1)
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_ten_model_stages_and_checkpoint_reuse(self):
        called = []
        def provider(path, payload):
            self.assertEqual(path, "/chat/completions")
            self.assertNotIn("tools", payload)
            stage = json.loads(payload["messages"][1]["content"])["stage"]
            called.append(stage)
            answer = {
                "classification": "SUPERSEDED" if
                    stage == "project_lifecycle_supersession" else "REVIEW",
                "rationale": "An independently fetched source describes change.",
                "claims": [{
                    "subject": "self-storage facility",
                    "relationship": "Historical change",
                    "source_index": 0, "quote": SOURCE_QUOTE}],
                "unresolved": ["Official current permit status"],
                "next_action": "Verify the latest official planning file",
            }
            return {"choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps(answer)}}],
                "usage": {"prompt_tokens": 700, "completion_tokens": 150}}
        first = run(self.root, paid=True, today=TODAY, token="test",
                    customer_profile="Industrial HVAC installers in Ontario",
                    enrich_sources=False, transport=provider)
        self.assertEqual(first["status"], "CHECKPOINTED_AI_REVIEW")
        self.assertEqual(called, list(STAGES))
        dossier = json.loads(Path(first["results"][0]["dossier"]).read_text())
        self.assertEqual(list(dossier["stages"]), list(STAGES))
        for stage in STAGES:
            self.assertEqual(dossier["stages"][stage]["accepted_literal_claim_count"], 1)
            self.assertFalse(dossier["stages"][stage]["verified_buyer"])
        overlay = json.loads((self.root /
            "GTA_RADAR_AI_TEN_CAPABILITIES_OVERLAY.json").read_text())
        item = overlay["projects"][self.record["record_id"]]
        self.assertTrue(item["ai_lifecycle_review_hold"])
        self.assertFalse(item["verified_buyer"])
        self.assertEqual(item["city"], "Toronto")
        again = run(self.root, paid=True, today=TODAY, token="test",
                    customer_profile="Industrial HVAC installers in Ontario",
                    enrich_sources=False,
                    transport=lambda *_: self.fail("Duplicate paid AI request"))
        self.assertEqual(again["results"][0]["stages"],
                         first["results"][0]["stages"])
        self.assertEqual(len(called), 10)

    def test_canonical_qualification_uses_ai_hold_without_claiming_buyer(self):
        v8 = self.root / "GTA_RADAR_V8_PENDING_QUEUE.csv"
        with v8.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "project_id", "city", "address", "source_keys",
                "description", "record_source_url", "current_source_status"])
            writer.writeheader()
            writer.writerow({
                "project_id": self.record["record_id"],
                "city": "Toronto", "address": self.record["address"],
                "source_keys": self.record["application_id"],
                "description": self.record["project_description"],
                "record_source_url": self.record["source_url"],
                "current_source_status": "Under Review"})
            writer.writerow({
                "project_id": "test:active:2026",
                "city": "Toronto", "address": "99 Example Rd",
                "source_keys": "26-987654",
                "description": "New industrial warehouse",
                "record_source_url": "https://example.org/newpermit",
                "current_source_status": "Under Review"})
        overlay = {"projects": {self.record["record_id"]: {
            **self.record, "ai_lifecycle_review_hold": True,
            "ai_lifecycle_proposal": "SUPERSEDED",
            "ai_stage_status": {"project_lifecycle_supersession":
                                "SOURCE_GROUNDED_REVIEW_ONLY"},
            "ai_company_source_claims": [{"subject": "Talus",
                                           "source_url":
                                           "https://example.org/report"}],
            "verified_buyer": False}}}
        (self.root / "GTA_RADAR_AI_TEN_CAPABILITIES_OVERLAY.json").write_text(
            json.dumps(overlay), encoding="utf-8")
        qualified = qualification_build(self.root, today=TODAY, apply_ai=False)
        self.assertEqual(qualified["ai_ten_projects_integrated"], 1)
        self.assertEqual(qualified["ai_ten_lifecycle_review_holds"], 1)
        self.assertEqual([x["record_id"] for x in qualified["top10"]],
                         ["test:active:2026"])
        held = next(x for x in qualified["all_candidates"]
                    if x["record_id"] == self.record["record_id"])
        self.assertTrue(held["ai_ten_lifecycle_hold"])
        self.assertFalse(held["buyer_verified"])

    def test_official_permit_only_skips_wasteful_model_stages(self):
        self.probe.write_text(json.dumps({"reviews": [{
            "record_id": self.record["record_id"], "city": "Toronto",
            "independently_fetched_context": [{
                "url": "https://example.org/permit",
                "identity": "EXACT_OFFICIAL_ARCGIS_APPLICATION",
                "excerpt": 'PERMITNUMBER 21170364S4505TLAB; '
                           '611 Keele St, Toronto, ON. Applied',
                "role_excerpt": "", "retrieved_on": "2026-11-15"
            }]
        }]}), encoding="utf-8")
        calls = []
        def provider(path, payload):
            self.assertEqual(path, "/chat/completions")
            calls.append(json.loads(payload["messages"][1]["content"])["stage"])
            return {"choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps({"classification": "UNKNOWN",
                                       "claims": []})}}],
                "usage": {"prompt_tokens": 700, "completion_tokens": 60}}
        output = run(self.root, paid=True, token="test", today=TODAY,
                     discover=False, enrich_sources=False,
                     transport=provider)
        dossier = json.loads(Path(output["results"][0]["dossier"]).read_text())
        self.assertNotIn("buyer_contact_path", calls)
        self.assertNotIn("procurement_award_status", calls)
        self.assertNotIn("technical_documents_equipment", calls)
        self.assertNotIn("early_investment_signals", calls)
        self.assertEqual(dossier["stages"]["procurement_award_status"]["status"],
                         "INSUFFICIENT_SOURCE_CONTEXT_NO_MODEL_CALL")

    def test_stale_different_house_number_is_not_source_evidence(self):
        self.probe.write_text(json.dumps({"reviews": [{
            "record_id": self.record["record_id"], "city": "Toronto",
            "independently_fetched_context": [{
                "url": "https://example.org/nearby",
                "identity": "SAME_ADDRESS_COMPANY_CONTEXT_NOT_LINKED",
                "excerpt": "1611 Keele St, Toronto, ON — Nearby Trading Inc.",
                "role_excerpt": "", "retrieved_on": "2026-11-15"}]
        }]}), encoding="utf-8")
        self.assertEqual(_evidence(self.root, self.record, TODAY), [])

    def test_company_enrichment_finds_source_without_prior_company_name(self):
        db = v5._ledger(self.root / "v5_ai_budget.sqlite")
        calls = []
        try:
            def provider(endpoint, payload):
                calls.append(endpoint)
                if endpoint == "/v1/tools/search":
                    return {"results": [
                        {"url": "https://example.org/irrelevant",
                         "snippet": "Unrelated real estate elsewhere"},
                        {"url": "https://example.org/business",
                         "snippet": "611 Keele St Toronto development company"}
                    ]}
                if endpoint == "/v1/tools/fetch":
                    self.assertEqual(payload["url"],
                                     "https://example.org/business")
                    return {"content":
                        "611 Keele St Toronto: Acme Group is the developer"}
                self.fail(endpoint)
            docs, status = source_enrich(
                self.root, self.record, "company_entity_relationships",
                {}, [], "test", db, TODAY, 0, transport=provider)
            self.assertEqual(status, "FETCHED_SOURCE_CONTEXT")
            self.assertEqual(len(docs), 1)
            self.assertIn("Acme Group", docs[0]["content"])
            self.assertEqual(calls, ["/v1/tools/search", "/v1/tools/fetch"])
        finally:
            db.close()

    def test_company_contact_source_enrichment_uses_fetch_not_snippets(self):
        previous = {"company_entity_relationships": {"claims": [{
            "subject": "Business Point",
            "literal_quote": "Business Point is the developer",
            "source_url": "https://example.org/project"}]}}
        requests = []
        def provider(endpoint, payload):
            requests.append(endpoint)
            if endpoint == "/v1/tools/search":
                self.assertIn("Business Point", payload["query"])
                return {"results": [{"url": "https://businesspoint.example/contact",
                                     "snippet": "Business Point official contact"}]}
            if endpoint == "/v1/tools/fetch":
                return {"content": "Business Point contact us: info@businesspoint.example"}
            self.fail(endpoint)
        db = v5._ledger(self.root / "v5_ai_budget.sqlite")
        try:
            sources, status = source_enrich(
                self.root, self.record, "buyer_contact_path", previous, [],
                "test", db, TODAY, 0, transport=provider)
            self.assertEqual(status, "FETCHED_SOURCE_CONTEXT")
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["identity"],
                             "SAME_NAMED_COMPANY_CONTACT_CONTEXT_NOT_BUYER")
            self.assertIn("info@businesspoint.example", sources[0]["content"])
            self.assertFalse(sources[0]["project_role_verified"])
            again, _ = source_enrich(
                self.root, self.record, "buyer_contact_path", previous, [],
                "test", db, TODAY, 0,
                transport=lambda *_: self.fail("No paid repeat"))
            self.assertEqual(sources, again)
            self.assertEqual(requests, ["/v1/tools/search", "/v1/tools/fetch"])
        finally:
            db.close()

    def test_quote_hallucination_is_not_supported(self):
        sources = _evidence(self.root, self.record, TODAY)
        self.assertEqual(len(sources), 1)
        self.assertEqual(_verified_claims({"claims": [{
            "subject": "Imaginary contractor", "relationship": "Confirmed",
            "source_index": 0, "quote":
                "Imaginary contractor won all unawarded trade packages"}]},
            sources), [])

    def test_company_name_must_appear_in_literal_quote(self):
        sources = _evidence(self.root, self.record, TODAY)
        answer = {"claims": [{
            "subject": "Fabricated Construction Inc.",
            "relationship": "Developer",
            "source_index": 0, "quote": SOURCE_QUOTE}]}
        self.assertEqual(_verified_claims(
            answer, sources, "company_entity_relationships"), [])
        self.assertEqual(_verified_claims(
            answer, sources, "buyer_contact_path"), [])

    def test_missing_source_never_spends_on_invented_evidence(self):
        self.probe.unlink()
        called = []
        result = run(self.root, paid=True, today=TODAY, token="test",
                     customer_profile="Industrial HVAC", discover=False,
                     enrich_sources=False,
                     transport=lambda *a: called.append(a))
        self.assertEqual(called, [])
        dossier = json.loads(Path(result["results"][0]["dossier"]).read_text())
        self.assertTrue(all(
            x["status"] == "NO_INDEPENDENT_EVIDENCE"
            for name, x in dossier["stages"].items()
            if name != "customer_specific_supplier_fit"))
        self.assertFalse(dossier["outreach_authorized"])

    def test_no_customer_profile_explicitly_holds_matching(self):
        result = run(self.root, paid=True, today=TODAY, token="test",
                     enrich_sources=False,
                     transport=lambda path, payload: {
                         "choices": [{"finish_reason": "stop",
                                      "message": {"content": json.dumps({
                                          "classification": "UNKNOWN",
                                          "claims": []})}}],
                         "usage": {"prompt_tokens": 750,
                                   "completion_tokens": 50}})
        dossier = json.loads(Path(result["results"][0]["dossier"]).read_text())
        self.assertEqual(dossier["stages"]["customer_specific_supplier_fit"][
            "status"], "CUSTOMER_PROFILE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
