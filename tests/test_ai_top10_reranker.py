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
