"""AI role extraction from real page passages; source identity and buyer holds."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_ai_company_role_evidence import check_roles, buyer_hypothesis
from gta_ai_top10_reranker import run as ai_run
from gta_commercial_qualification_review import (
    build, CLIENT, TOP_OUT,
)
from gta_project_company_evidence_graph import build as graph_build


DAY=dt.date(2026,11,14)
ROLE_TEXT="The registered owner of the industrial building is Acme Logistics Ltd."
TENANT_TEXT="The tenant at the industrial site is Staples Canada Inc."


class RoleEvidenceTests(unittest.TestCase):
    def source(self,identity="EXACT_APPLICATION_ID_IN_FETCHED_TEXT"):
        return [{"url":"https://www.toronto.ca/council/2026-project-document",
                 "identity":identity,
                 "excerpt":"Application 25 249692 ESC21CD. "+ROLE_TEXT,
                 "role_excerpt":ROLE_TEXT,
                 "retrieved_on":"2026-11-14"}]

    def test_role_literal_exact_id_review_only(self):
        claims, rejected=check_roles([{
            "role":"OWNER","organization":"Acme Logistics Ltd.",
            "source_j":0,"quote":ROLE_TEXT}],self.source())
        self.assertEqual(rejected,0)
        self.assertEqual(len(claims),1)
        self.assertEqual(claims[0]["role"],"OWNER")
        self.assertTrue(claims[0]["project_role_supported_for_review"])
        self.assertEqual(claims[0]["evidence_level"],
                         "EXACT_APPLICATION_ROLE_SOURCE_REVIEW_ONLY")
        self.assertFalse(claims[0]["buyer_verified"])

    def test_same_address_company_context_not_project_role(self):
        claims, rejected=check_roles([{
            "role":"OWNER","organization":"Acme Logistics Ltd.",
            "source_j":0,"quote":ROLE_TEXT}],
            self.source("SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED"))
        self.assertEqual(rejected,0)
        self.assertEqual(len(claims),1)
        self.assertFalse(claims[0]["project_role_supported_for_review"])
        self.assertEqual(claims[0]["evidence_level"],
                         "SAME_ADDRESS_SITE_CONTEXT_NOT_PROJECT_ROLE")

    def test_hallucinated_role_or_name_is_rejected(self):
        claims, rejected=check_roles([
            {"role":"CONTRACTOR","organization":"Acme Logistics Ltd.",
             "source_j":0,"quote":ROLE_TEXT},
            {"role":"OWNER","organization":"Unknown Builders Inc.",
             "source_j":0,"quote":ROLE_TEXT},
            {"role":"OWNER","organization":"Acme Logistics Ltd.",
             "source_j":2,"quote":ROLE_TEXT},
        ],self.source())
        self.assertEqual(claims,[])
        self.assertEqual(rejected,3)

    def test_buying_function_is_not_verified_contact(self):
        role=buyer_hypothesis({
            "function":"TENANT_FACILITIES",
            "reason":"The tenant may coordinate equipment fit-out procurement"})
        self.assertEqual(role["function"],"TENANT_FACILITIES")
        self.assertEqual(role["state"],"AI_HYPOTHESIS_NOT_BUYER_VERIFICATION")
        self.assertFalse(role["buyer_verified"])
        self.assertFalse(role["contact_verified"])
        unsupported=buyer_hypothesis({"function":"BOB_AT_416-555-1234",
                                      "reason":"confirmed buyer bob@example.com"})
        self.assertEqual(unsupported["function"],"UNKNOWN")
        self.assertNotIn("@",unsupported["reason"])


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        row={
            "opportunity_id":"CASE1","application_ids":"25249692ESC21CD",
            "city":"Toronto","address":"1430 Birchmount Road, Toronto, ON",
            "nature_of_work":"New industrial condominium warehouse expansion",
            "source_event_date":"2026-11-13",
            "source_event_date_basis":"OFFICIAL_APPLICATION_DATE_NOT_PUBLICATION",
            "stage_gate":"Under Review",
            "source_url":"https://www.toronto.ca/planning/current-development/",
        }
        with (self.root/CLIENT).open("w",encoding="utf-8-sig",newline="") as file:
            writer=csv.DictWriter(file,fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)

    def mock_provider(self, page):
        seen=[]
        def provider(path,payload):
            seen.append(path)
            if path=="/v1/tools/search":
                return {"results":[{
                    "url":"https://www.toronto.ca/council/2026-project-document",
                    "snippet":"Application 25 249692 ESC21CD; "+ROLE_TEXT}]}
            if path=="/v1/tools/fetch":
                return {"content":page}
            if path=="/chat/completions":
                data=json.loads(payload["messages"][1]["content"])
                self.assertEqual(len(data["projects"]),1)
                live=data["projects"][0]["live_sources"]
                self.assertTrue(live)
                answer={"reviews":[{
                    "i":0,"decision":"PREFER",
                    "reason":"New source-backed industrial facility scope",
                    "investigate":"Confirm general contractor buying authority",
                    "role_claims":[{
                        "organization":"Acme Logistics Ltd.","role":"OWNER",
                        "source_j":0,"quote":ROLE_TEXT}],
                    "buyer_function":{
                        "function":"GENERAL_CONTRACTOR_BUYOUT",
                        "reason":"A contractor may make equipment purchasing decisions"},
                }]}
                return {
                    "choices":[{"message":{"content":json.dumps(answer)},
                                "finish_reason":"stop"}],
                    "usage":{"prompt_tokens":1700,"completion_tokens":350,
                             "prompt_cache_hit_tokens":0,
                             "prompt_cache_miss_tokens":1700},
                }
            raise AssertionError(path)
        return provider,seen

    def test_paid_ai_roles_flow_to_graph_and_csv_review_only(self):
        page="Toronto application 25 249692 ESC21CD, November record. "+ROLE_TEXT
        provider,seen=self.mock_provider(page)
        result=ai_run(self.root,paid=True,key="test",today=DAY,transport=provider)
        self.assertEqual(result["status"],"AI_TOP10_REVIEW_ONLY")
        self.assertIn("/chat/completions",seen)
        self.assertIn("/v1/tools/fetch",seen)
        q=build(self.root,today=DAY)
        self.assertEqual(q["ai_exact_application_role_candidates"],1)
        self.assertEqual(q["verified_buyers"],0)
        top=q["top10"][0]
        self.assertEqual(top["ai_company_roles_review"][0]["organization"],
                         "Acme Logistics Ltd.")
        self.assertEqual(top["ai_buying_function_hypothesis"]["function"],
                         "GENERAL_CONTRACTOR_BUYOUT")
        self.assertFalse(top["buyer_verified"])
        graph=graph_build(self.root,now="2026-11-14T20:00:00+00:00")
        edges=[r for r in graph["edges"]
               if r.get("evidence_origin")=="AI_TOP10_EXACT_ID_QUOTED_ROLE_REVIEW_ONLY"]
        self.assertEqual(len(edges),1)
        self.assertEqual(edges[0]["role_claimed"],"PROPERTY_OWNER")
        self.assertTrue(edges[0]["role_quote_present"])
        self.assertFalse(edges[0]["buyer_verified"])
        self.assertEqual(graph["verified_buyers"],0)
        self.assertTrue((self.root/TOP_OUT).exists())
        with (self.root/TOP_OUT).open(encoding="utf-8-sig",newline="") as file:
            exported=list(csv.DictReader(file))
        self.assertIn("Acme Logistics Ltd.",exported[0]["ai_company_roles_review"])
        self.assertIn("GENERAL_CONTRACTOR_BUYOUT",exported[0]["ai_buying_function_hypothesis"])

    def test_only_address_context_does_not_create_project_graph_role(self):
        page=("1430 Birchmount Road has a separate construction application "
              "for the same site. "+ROLE_TEXT)
        provider,_=self.mock_provider(page)
        # The original application number is not in this fetched page.
        result=ai_run(self.root,paid=True,key="test",today=DAY,transport=provider)
        self.assertEqual(result["status"],"AI_TOP10_REVIEW_ONLY")
        q=build(self.root,today=DAY)
        self.assertEqual(q["ai_exact_application_role_candidates"],0)
        self.assertEqual(q["ai_same_address_company_mentions"],1)
        graph=graph_build(self.root,now="2026-11-14T20:00:00+00:00")
        self.assertEqual(graph["ai_top10_quote_supported_role_review_candidates"],0)
        self.assertEqual(graph["verified_project_company_roles"],0)


if __name__=="__main__":
    unittest.main()
