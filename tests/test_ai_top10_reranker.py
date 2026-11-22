"""Regression tests: DeepSeek participates in top-ten preselection, safely."""
import csv
from contextlib import closing
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from gta_ai_top10_reranker import run as ai_run, ATTEMPT
from gta_commercial_qualification_review import (
    build, run as shortlist_run, CLIENT, AI_REVIEW,
)


DAY = dt.date(2026,11,14)


class AITopTenSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, rows):
        keys = sorted(set().union(*(item.keys() for item in rows)))
        with (self.root/CLIENT).open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)

    def row(self, app, *, description="New industrial warehouse expansion",
            city="Toronto", date="2026-11-13", prior=False):
        return {
            "opportunity_id": app, "application_ids": app, "city": city,
            "address": app+" Example Road",
            "nature_of_work": description, "source_event_date": date,
            "source_event_date_basis": "OFFICIAL_FILING_DATE_NOT_PUBLICATION",
            "stage_gate": "Under Review", "named_company_role_unverified": "",
            "source_url": "https://planning.toronto.ca/active-development-applications/"+app+"/",
        }

    def transport(self, changes=None, counter=None):
        changes=changes or {}
        def send(path,payload):
            if counter is not None: counter.append(path)
            if path == "/v1/tools/search":
                return {"results": []}
            if path == "/v1/tools/fetch":
                return {"content": ""}
            self.assertEqual(path,"/chat/completions")
            user=json.loads(payload["messages"][1]["content"])
            reviews=[]
            for row in user["projects"]:
                decision=changes.get(row["project_id"],"NEUTRAL")
                reviews.append({
                    "i":row["i"],"decision":decision,
                    "reason":"Source-described scope and status; check newer file",
                    "investigate":"Review official current application and tender status",
                })
            return {
                "choices":[{"message":{"content":json.dumps({"reviews":reviews})},
                            "finish_reason":"stop"}],
                "usage":{"prompt_tokens":1800,
                         "completion_tokens":360,
                         "prompt_cache_hit_tokens":0,
                         "prompt_cache_miss_tokens":1800},
            }
        return send

    def test_ai_changes_internal_order_but_never_buyer_status(self):
        self.write([self.row("A"),self.row("B"),self.row("C")])
        baseline=build(self.root,today=DAY)
        self.assertEqual(baseline["top10"][0]["record_id"],"A")
        calls=[]
        result=ai_run(self.root, paid=True, key="test", today=DAY,
                      transport=self.transport(
                          {"A":"DEPRIORITIZE","B":"PREFER","C":"NEUTRAL"},calls))
        self.assertEqual(result["status"],"AI_TOP10_REVIEW_ONLY")
        self.assertEqual(result["reviewed_count"],3)
        self.assertEqual(result["paid_model_calls"],3)
        self.assertEqual(calls.count("/chat/completions"),3)
        after=build(self.root,today=DAY)
        self.assertEqual(after["ai_preselection_reviewed_count"],3)
        self.assertEqual(after["top10"][0]["record_id"],"B")
        self.assertEqual(after["top10"][0]["ai_preselection_decision"],"PREFER")
        self.assertEqual(after["verified_buyers"],0)
        self.assertEqual(after["verified_open_supplier_contracts"],0)
        self.assertFalse(after["outreach_authorized"])
        self.assertFalse(after["top10"][0]["buyer_verified"])
        self.assertEqual(after["top10"][0]["contact_email"],"")
        self.assertTrue((self.root/ATTEMPT).exists())

    def test_no_paid_flag_is_no_network_and_no_ledger(self):
        self.write([self.row("A"),self.row("B")])
        report=ai_run(self.root, paid=False, key="test", today=DAY,
                      transport=lambda *_:self.fail("NO_NETWORK_ALLOWED"))
        self.assertEqual(report["paid_model_calls"],0)
        self.assertEqual(report["status"],"FREE_PREFLIGHT_NOT_SUBMITTED")
        self.assertFalse((self.root/"v5_ai_budget.sqlite").exists())


    def test_partial_source_check_produces_labeled_internal_review(self):
        from unittest.mock import patch
        self.write([self.row("A"), self.row("B")])
        def check(_root, record, *_args, **_kwargs):
            complete = record["record_id"] != "A"
            return ({
                "record_id": record["record_id"],
                "city": record["city"],
                "complete": complete,
                "checked_on": DAY.isoformat(),
                "sources": [{
                    "url": record["source_url"],
                    "identity": "EXACT_APPLICATION_ID_IN_FETCHED_TEXT",
                    "excerpt": "Project record " + record["application_id"],
                    "role_excerpt": "",
                    "retrieved_on": DAY.isoformat(),
                }],
                "issues": [] if complete else ["SEARCH_LEDGER_HELD_OR_PREVIOUS"],
            }, False)
        with patch("gta_ai_top10_reranker.recheck_project", side_effect=check):
            result = ai_run(
                self.root, paid=True, key="test", today=DAY,
                transport=self.transport())
        self.assertEqual(result["status"], "AI_TOP10_REVIEW_ONLY")
        self.assertTrue(result["source_evidence_incomplete"])
        self.assertEqual(result["live_checks_completed"], 1)
        self.assertEqual(result["partial_source_checks"][0]["record_id"], "A")
        self.assertEqual(result["paid_model_calls"], 2)
        self.assertFalse(result["verified_buyers"])
        after = build(self.root, today=DAY)
        findings = {x["record_id"]: x for x in after["top10"]}
        self.assertFalse(findings["A"]["ai_live_recheck_complete"])
        self.assertIn("SEARCH_LEDGER_HELD_OR_PREVIOUS",
                      findings["A"]["ai_live_source_check_issues"])
        self.assertTrue(findings["B"]["ai_live_recheck_complete"])
        self.assertFalse(after["outreach_authorized"])

    def test_existing_exact_batch_checkpoint_idempotent(self):
        self.write([self.row("A"),self.row("B")])
        counter=[]
        first=ai_run(self.root,paid=True,key="test",today=DAY,
                     transport=self.transport(counter=counter))
        second=ai_run(self.root,paid=True,key="test",today=DAY,
                      transport=lambda *_:self.fail("Already reviewed batch must not retry"))
        self.assertEqual(first["status"],"AI_TOP10_REVIEW_ONLY")
        self.assertEqual(second["status"],"AI_TOP10_REVIEW_ONLY")
        self.assertEqual(second["paid_model_calls"],0)
        self.assertEqual(second["reviewed_count"],2)
        self.assertEqual(counter.count("/chat/completions"),2)

    def test_revised_description_invalidates_saved_ai_without_hallucinating(self):
        self.write([self.row("A"),self.row("B")])
        ai_run(self.root,paid=True,key="test",today=DAY,
               transport=self.transport({"B":"PREFER"}))
        self.write([self.row("A"),self.row("B",description="Existing old storage building")])
        q=build(self.root,today=DAY)
        self.assertEqual(q["ai_preselection_reviewed_count"],0)
        self.assertEqual(q["ai_preselection_status"],"STALE_OR_INCOMPLETE_REVIEW_IGNORED")

    def test_incomplete_or_invalid_batch_cannot_rerank(self):
        self.write([self.row("A"),self.row("B")])
        def invalid(path,payload):
            if path == "/v1/tools/search":
                return {"results":[]}
            if path == "/v1/tools/fetch":
                return {"content":""}
            return {"choices":[{"message":{"content":json.dumps(
                {"reviews":[]})},
                "finish_reason":"stop"}],
                "usage":{"prompt_tokens":900,"completion_tokens":50}}
        result=ai_run(self.root,paid=True,key="test",today=DAY,transport=invalid)
        self.assertTrue(result["status"].startswith("AI_PRESELECTION_INCOMPLETE_"))
        self.assertFalse((self.root/AI_REVIEW).exists())
        q=build(self.root,today=DAY)
        self.assertEqual(q["ai_preselection_reviewed_count"],0)


    def test_invalid_paid_response_is_preserved_for_offline_diagnosis(self):
        self.write([self.row("A")])
        def invalid(path, payload):
            if path == "/v1/tools/search":
                return {"results": []}
            if path == "/v1/tools/fetch":
                return {"content": ""}
            return {"choices": [{"message": {"content": '{"reviews":[]}'},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 900, "completion_tokens": 50}}
        result = ai_run(self.root, paid=True, key="test", today=DAY,
                        transport=invalid)
        self.assertIn("AI_REVIEW_INVALID_ValueError", result["status"])
        self.assertEqual(result["failed_project_id"], "A")
        self.assertIn("AI_PRESELECTION_REVIEW_COUNT_INVALID",
                      result["validation_error"])
        raw_path = Path(result["failed_response_file"])
        self.assertTrue(raw_path.is_file())
        self.assertEqual(json.loads(raw_path.read_text(encoding="utf-8"))
                         ["choices"][0]["message"]["content"], '{"reviews":[]}')
        self.assertFalse((self.root / AI_REVIEW).exists())

    def test_malformed_json_one_budgeted_repair_preserves_whole_batch(self):
        self.write([self.row("A"), self.row("B")])
        calls=[]
        def transport(path, payload):
            if path == "/v1/tools/search": return {"results":[]}
            if path == "/v1/tools/fetch": return {"content":""}
            self.assertEqual(path,"/chat/completions")
            calls.append(path)
            project=json.loads(payload["messages"][1]["content"])["projects"][0]
            if project["project_id"]=="A" and len(calls)==1:
                content='{"reviews": [THIS IS NOT VALID JSON'
            else:
                content=json.dumps({"reviews":[{
                    "i":0, "decision":"NEUTRAL",
                    "reason":"Investigate official exact-file notice",
                    "investigate":"Check if plant equipment remains unawarded",
                }]})
            return {"choices":[{"message":{"content":content},
                     "finish_reason":"stop"}],
                "usage":{"prompt_tokens":500,"completion_tokens":110}}
        result=ai_run(self.root,paid=True,key="test",today=DAY,transport=transport)
        self.assertEqual(result["status"],"AI_TOP10_REVIEW_ONLY")
        self.assertEqual(result["reviewed_count"],2)
        self.assertEqual(result["paid_model_calls"],3)
        self.assertEqual(result["recovered_json_batches"],1)
        self.assertEqual(len(calls),3)
        self.assertFalse(result["verified_buyers"])
        self.assertFalse(result["verified_open_supplier_packages"])

    def test_irrecoverable_json_does_not_discard_later_checkpoints(self):
        self.write([self.row("A"),self.row("B")])
        calls=[]
        def send(path,payload):
            if path=="/v1/tools/search":return {"results":[]}
            if path=="/v1/tools/fetch":return {"content":""}
            project=json.loads(payload["messages"][1]["content"])["projects"][0]
            calls.append(project["project_id"])
            content=(
                "not JSON at all" if project["project_id"]=="A" else
                json.dumps({"reviews":[{"i":0,"decision":"NEUTRAL",
                    "reason":"Check actual municipal project scope",
                    "investigate":"Confirm source and procurement stage"}]}))
            return {"choices":[{"message":{"content":content},
                        "finish_reason":"stop"}],
                    "usage":{"prompt_tokens":500,"completion_tokens":110}}
        first=ai_run(self.root,paid=True,key="test",today=DAY,transport=send)
        self.assertEqual(first["reviewed_count"],1)
        self.assertEqual(first["paid_model_calls"],3)
        self.assertEqual(len(first["failed_reviews"]),1)
        self.assertEqual(first["failed_reviews"][0]["record_id"],"A")
        self.assertEqual(calls,["A","A","B"])
        self.assertIn("INCOMPLETE",first["status"])
        self.assertFalse((self.root/AI_REVIEW).exists())
        again=ai_run(self.root,paid=True,key="test",today=DAY,
                     transport=lambda *_:self.fail("No repeat paid calls permitted"))
        self.assertEqual(again["paid_model_calls"],0)
        self.assertEqual(again["reviewed_count"],1)
        self.assertGreaterEqual(again["reused_paid_response_count"],1)

    def test_evidence_quote_can_reference_supplied_role_excerpt(self):
        from gta_ai_top10_reranker import _validate
        row = {"city": "Toronto", "record_id": "A"}
        source = {
            "identity": "EXACT_APPLICATION_ID_IN_FETCHED_TEXT",
            "url": "https://example.org/planning",
            "retrieved_on": DAY.isoformat(),
            "excerpt": "Planning file A.",
            "role_excerpt": "Registered owner: Acme Development Inc.",
        }
        response = {
            "choices": [{"message": {"content": json.dumps({"reviews": [{
                "i": 0, "decision": "NEUTRAL", "reason": "Investigate",
                "investigate": "Find the construction tender",
                "evidence_j": 0,
                "evidence_quote": "Registered owner: Acme Development Inc.",
                "role_claims": [{"organization": "Acme Development Inc.",
                                 "role": "OWNER", "source_j": 0,
                                 "quote": "Registered owner: Acme Development Inc."}]
            }]})}, "finish_reason": "stop"}]
        }
        parsed = _validate(
            response, 1, [row], {("toronto", "A"): {"sources": [source]}})
        self.assertEqual(len(parsed[0]["role_candidates"]), 1)
        self.assertEqual(parsed[0]["cited_source"]["quote"],
                         "Registered owner: Acme Development Inc.")


    def test_company_search_queries_fit_deepseek_api_limit(self):
        from gta_top10_live_source_recheck import _queries, _identity
        row = {"address": "238 Glidden Road, Brampton",
               "city": "Brampton",
               "application_id": "26-185633-000-00"}
        queries = _queries(row)
        self.assertTrue(all(1 <= len(q) <= 128 for q in queries))
        self.assertTrue(any("company business occupant" in q for q in queries))
        identity, excerpt = _identity(
            "Brenntag Canada Inc. 238 Glidden Road Brampton. Contact our office.", row)
        self.assertEqual(identity, "SAME_ADDRESS_COMPANY_CONTEXT_NOT_LINKED")
        self.assertIn("Brenntag Canada Inc.", excerpt)
        identity, _ = _identity(
            "26-185633-000-00 238 Glidden Road addition shell", row)
        self.assertEqual(identity, "EXACT_APPLICATION_ID_IN_FETCHED_TEXT")

    def test_site_company_evidence_cannot_claim_a_buyer(self):
        from gta_ai_company_role_evidence import check_site_mentions
        sources = [{
            "url": "https://example.org/company",
            "identity": "SAME_ADDRESS_COMPANY_CONTEXT_NOT_LINKED",
            "excerpt": "Brenntag Canada Inc. 238 Glidden Road, Brampton.",
            "role_excerpt": "",
        }]
        claims, rejected = check_site_mentions([
            {"organization": "Brenntag Canada Inc.", "source_j": 0,
             "quote": "Brenntag Canada Inc. 238 Glidden Road"},
            {"organization": "Invented Buyer Ltd.", "source_j": 0,
             "quote": "Invented Buyer Ltd."}], sources)
        self.assertEqual((len(claims), rejected), (1, 1))
        self.assertFalse(claims[0]["project_role_supported_for_review"])
        self.assertFalse(claims[0]["buyer_verified"])

    def test_optional_web_research_uses_independent_fetch_and_checkpoint(self):
        from gta_top10_live_source_recheck import model_directed_company_search
        import v5_investigator as v5
        calls = []
        row = {
            "record_id": "A", "city": "Brampton",
            "address": "238 Glidden Road",
            "application_id": "26-185633-000-00",
            "project_description": "Industrial addition",
            "source_url": "https://example.org/original",
        }
        def transport(path, payload):
            calls.append(path)
            if path == "/chat/completions":
                self.assertTrue(any(
                    x["type"] == "deepseek_web_search"
                    for x in payload["tools"]))
                self.assertNotIn("response_format", payload)
                return {
                    "choices": [{"finish_reason": "stop", "message": {
                        "content": "Company appears at address, not tied to permit.",
                        "annotations": [{"url_citation": {
                            "url": "https://example.org/brenntag"}}]}}],
                    "usage": {"prompt_tokens": 1100, "completion_tokens": 130,
                              "server_tool_use": {"tool_search": 1, "tool_fetch": 1}},
                }
            if path == "/v1/tools/fetch":
                return {"content": "Brenntag Canada Inc., 238 Glidden Road, Brampton. Contact."}
            self.fail("unexpected request " + path)
        db = v5._ledger(self.root / "v5_ai_budget.sqlite")
        try:
            first = model_directed_company_search(
                self.root, row, "test", db, DAY, 0, transport=transport)
            second = model_directed_company_search(
                self.root, row, "test", db, DAY, 0,
                transport=lambda *_: self.fail("Paid web research was repeated"))
        finally:
            db.close()
        self.assertEqual(first["status"], "FETCHED_CONTEXT_ONLY")
        self.assertEqual(len(first["sources"]), 1)
        self.assertEqual(first["sources"][0]["identity"],
                         "SAME_ADDRESS_COMPANY_CONTEXT_NOT_LINKED")
        self.assertEqual(second["record_id"], "A")
        self.assertEqual(calls, ["/chat/completions", "/v1/tools/fetch"])

    def test_qualification_retains_site_name_without_selling_lead(self):
        from gta_ai_company_role_evidence import check_site_mentions
        from gta_ai_top10_reranker import _validate
        row = {"city": "Brampton", "record_id": "A"}
        source = {
            "url": "https://example.org/company",
            "identity": "SAME_ADDRESS_COMPANY_CONTEXT_NOT_LINKED",
            "excerpt": "Brenntag Canada Inc. 238 Glidden Road Brampton.",
            "role_excerpt": "",
        }
        answer = {"choices": [{"finish_reason": "stop",
            "message": {"content": json.dumps({"reviews": [{
                "i": 0, "decision": "NEUTRAL", "reason": "Company at site",
                "investigate": "Confirm the permit applicant",
                "site_company_mentions": [{
                    "organization": "Brenntag Canada Inc.", "source_j": 0,
                    "quote": "Brenntag Canada Inc. 238 Glidden Road"}]
            }]})}}]}
        checked = _validate(answer, 1, [row],
                            {("brampton", "A"): {"sources": [source]}})
        self.assertEqual(len(checked[0]["site_company_candidates"]), 1)
        self.assertEqual(checked[0]["role_candidates"], [])

    def test_http402_is_not_a_charge_and_prevents_result(self):
        self.write([self.row("A"),self.row("B")])
        def reject(path,payload):
            raise HTTPError("https://api.deepseek.com/chat/completions",
                            402, "Payment Required",None,None)
        result=ai_run(self.root,paid=True,key="test",today=DAY,transport=reject)
        self.assertIn("PROVIDER_HTTP_402_ACCOUNT_BALANCE",result["status"])
        self.assertFalse((self.root/AI_REVIEW).exists())
        import sqlite3
        with closing(sqlite3.connect(self.root/"v5_ai_budget.sqlite")) as db:
            rows=db.execute("SELECT reserved,actual,status FROM spends").fetchall()
        self.assertEqual(rows,[(0.0,0.0,"NONBILLABLE")])

    def test_duplicate_application_number_whitespace_variation(self):
        a=self.row("25 249692 ESC 21 CD")
        b=self.row("25249692ESC21CD")
        a["opportunity_id"]="ROW_A"
        b["opportunity_id"]="ROW_B"
        self.write([a,b])
        result=build(self.root,today=DAY)
        self.assertEqual(result["presentation_duplicates_suppressed"],1)
        self.assertEqual(result["deduplicated_review_candidates"],1)

    def test_ai_cannot_create_new_opportunities_or_invent_contacts(self):
        self.write([self.row("A",description="New industrial plant expansion")])
        q=build(self.root,today=DAY,apply_ai=False)
        malicious={
            "status":"AI_TOP10_REVIEW_ONLY",
            "source_snapshot_only":True,"applies_to_top10":True,
            "input_fingerprint":q["ai_preselection_input_fingerprint"],
            "reviews":[{"city":"Toronto","record_id":"UNRELATED",
                        "decision":"PREFER","reason":"Buyer verified",
                        "next_check":"Send outreach"}]}
        (self.root/AI_REVIEW).write_text(json.dumps(malicious),encoding="utf-8")
        after=shortlist_run(self.root,today=DAY)
        self.assertEqual(after["ai_preselection_reviewed_count"],0)
        self.assertEqual(after["verified_buyers"],0)
        reloaded=build(self.root,today=DAY)
        self.assertEqual(reloaded["top10"][0]["contact_email"],"")


if __name__=="__main__":
    unittest.main()
