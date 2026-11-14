"""Regression cases drawn from the November 14 AI review evidence archive.

All fixtures are offline synthetic excerpts illustrating the *exact* observed
issue types: Burbank registered owner vs developer, Markham civic address
variant, Eglinton municipal planner, Dundas no corroborating page. The real
uploaded research files are not committed to the public repository.
"""
import json
import tempfile
import unittest
from pathlib import Path

from gta_ai_project_evidence_bridge import build, run, OUTPUT
from gta_ai_project_intelligence_refresh import run as refresh
from gta_project_company_evidence_graph import build as graph_build
from gta_supplier_verification_gate import build as procurement_build


class AIProjectBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.reviews = self.root / "AGENT_HARNESS_REVIEW" / "PROJECT_RESEARCH"
        self.reviews.mkdir(parents=True)

    def saved(self, appid, address, model, sources=None, *, name=None, **kwargs):
        p = {
            "project_id": "toronto_development_applications:" + appid,
            "address": address, "input_hash": "a"*64,
            "source_url": "https://gis.toronto.ca/FeatureServer/60/query",
            "research_status": "AI_REVIEW_ONLY",
            "qualification_status": "RESEARCH_ONLY",
            "sale_ready": False,
            "model_suggestions": model,
            "sources": sources or [],
            **kwargs,
        }
        path = self.reviews / ("AI_PROJECT_" + (name or appid) + ".json")
        path.write_text(json.dumps(p), encoding="utf-8")
        return path

    def official(self, appid, *, address, status="Under Review",
                 description="Commercial redevelopment", planner=""):
        return {
            "url": "https://gis.toronto.ca/FeatureServer/60/query",
            "kind": "OFFICIAL_ARCGIS_ATTRIBUTES",
            "page_identity": "EXACT_CURRENT_PERMIT_ID_IN_PAGE",
            "text": json.dumps({"attributes": [{
                "APPLICATION_NUMBER": appid,
                "FULL_ADDRESS": address,
                "STATUS_DESC": status,
                "FOLDERDESCRIPTION": description,
                "ASSIGNEDPLANNER2": planner,
                "LATEST_MILESTONE_DATE": "1792641600000",
            }]}),
        }

    def test_sheppard_owner_supported_developer_role_not_inferred(self):
        app="22217053NNY17OZ"
        doc = {
            "url": "https://www.toronto.ca/legdocs/mmis/2026/cc/file.pdf",
            "kind": "SEARCH_PAGE_CONTENT",
            "page_identity": "EXACT_CURRENT_PERMIT_ID_IN_PAGE",
            "text": ("Application 22217053NNY17OZ: We are the lawyers "
                     "for Burbank Heights Development Inc., registered owner of "
                     "690-720 Sheppard Avenue East. Offer of settlement only."),
        }
        self.saved(app, "690 SHEPPARD AVE E", {
            "owner":"Burbank Heights Development Inc.",
            "developer":"Burbank Heights Development Inc.",
            "project_stage":"OLT proceedings ongoing; approval is not confirmed",
            "buyer_fit":"Residential towers"},
            [self.official(app, address="692 SHEPPARD AVE E",
                           status="OMB Approved",description="705 residential units"),
             doc])
        report = build(self.root)
        self.assertEqual(report["project_candidates"],1)
        self.assertEqual(len(report["role_claims"]),1)
        self.assertEqual(report["role_claims"][0]["role"],"PROPERTY_OWNER")
        self.assertEqual(report["role_claims"][0]["organization"],
                         "Burbank Heights Development Inc.")
        self.assertFalse(report["role_claims"][0]["verified_buyer"])
        holds = {h["reason"] for h in report["holds"]}
        self.assertIn("ROLE_NOT_EXPLICIT_IN_EXACT_ID_SOURCE",holds)
        self.assertIn("AI_LIFECYCLE_CONTRADICTS_OFFICIAL_STATUS",holds)
        self.assertIn("APPLICATION_ADDRESS_VARIANT_REVIEW",holds)
        self.assertEqual(report["projects"][0]["official_milestone_date"],"2026-10-22")
        self.assertEqual(report["projects"][0]["date_basis"],
                         "OFFICIAL_MILESTONE_NOT_PUBLICATION")

    def test_markham_address_conflict_requires_review_not_auto_merge(self):
        app="26107153ESC23SA"
        self.saved(app,"2290 MARKHAM RD",{
            "owner":"", "developer":"", "project_stage":"NOAC Issued"},
            [self.official(app,address="2250 MARKHAM RD",
                           status="NOAC Issued",
                           description="Five-storey self-storage warehouse and retail amendment")])
        report=build(self.root)
        self.assertEqual(report["project_candidates"],1)
        self.assertEqual(report["projects"][0]["commercial_sector_for_review"],
                         "INDUSTRIAL_OR_WAREHOUSE_RESEARCH")
        self.assertEqual(report["projects"][0]["maturity_for_review"],
                         "POST_APPROVAL_OR_ISSUANCE_RECHECK")
        self.assertEqual(report["projects"][0]["official_address"],"2250 MARKHAM RD")
        self.assertFalse(report["projects"][0]["sale_ready"])
        self.assertEqual(report["role_claims"],[])
        self.assertTrue(any(x["reason"]=="APPLICATION_ADDRESS_VARIANT_REVIEW"
                            for x in report["holds"]))

    def test_eglinton_planner_cannot_become_buyer_or_developer(self):
        app="26151476ESC20OZ"
        self.saved(app,"2363 EGLINTON AVE E",{
            "contact":"Tyler Hughes","owner":"","developer":"","operator":""},
            [self.official(app,address="2365 EGLINTON AVE E",
                           status="Under Review",
                           description="Mixed-use building residential retail",
                           planner="Tyler Hughes")])
        item=build(self.root)["projects"][0]
        self.assertEqual(item["municipal_contact"]["name"],"Tyler Hughes")
        self.assertFalse(item["municipal_contact"]["is_commercial_buyer"])
        self.assertEqual(item["claims"],[])

    def test_unverified_dundas_source_only_stays_out_of_graph(self):
        self.saved("20198309STE13SA","166 DUNDAS ST E",
                   {"project_stage":"Under review"},[])
        self.assertEqual(build(self.root)["project_candidates"],0)
        self.assertIn("NO_EXACT_OFFICIAL_APPLICATION_ATTRIBUTES",
                      {x["reason"] for x in build(self.root)["holds"]})

    def test_forged_identity_marker_not_enough_without_literal_id(self):
        app="26107153ESC23SA"
        wrong=self.official("26107153ESC23SB",address="2250 MARKHAM RD")
        wrong["page_identity"]="EXACT_CURRENT_PERMIT_ID_IN_PAGE"
        self.saved(app,"2290 MARKHAM RD",{"owner":"Fake Ltd"},[wrong])
        self.assertEqual(build(self.root)["project_candidates"],0)

    def test_source_literal_without_role_is_not_proof(self):
        app="26107153ESC23SA"
        s=self.official(app,address="2250 MARKHAM RD")
        s["text"]+=" Company Blue Capital is mentioned with no role."
        self.saved(app,"2250 MARKHAM RD",
                   {"owner":"Blue Capital"},[s])
        report=build(self.root)
        self.assertEqual(report["role_claims"],[])
        self.assertEqual(report["project_candidates"],1)

    def test_bridge_refresh_populates_existing_review_gate_without_promoting(self):
        app="22217053NNY17OZ"
        doc={"url":"https://toronto.ca/file.pdf","kind":"SEARCH_PAGE_CONTENT",
             "page_identity":"EXACT_CURRENT_PERMIT_ID_IN_PAGE",
             "text":("22217053NNY17OZ: Burbank Heights Development Inc. is "
                     "registered owner of the site.")}
        self.saved(app,"690 SHEPPARD AVE E",
                   {"owner":"Burbank Heights Development Inc."},
                   [self.official(app,address="690 SHEPPARD AVE E",
                                  status="OMB Approved",
                                  description="Residential tower scheme"),doc])
        summary=refresh(self.root)
        self.assertEqual(summary["source_supported_ai_role_claims"],1)
        self.assertTrue((self.root/OUTPUT).is_file())
        self.assertTrue((self.root/"GTA_RADAR_COMPANY_ROLE_REVIEW_QUEUE.csv").is_file())
        graph=graph_build(self.root)
        self.assertEqual(graph["ai_source_supported_role_claims"],1)
        self.assertEqual(graph["claimed_relationships"],1)
        self.assertEqual(graph["project_candidates"],1)
        self.assertEqual(graph["verified_buyers"],0)
        gate=procurement_build(self.root)
        self.assertEqual(len(gate["role_queue"]),1)
        self.assertEqual(gate["role_queue"][0]["role_claimed"],"PROPERTY_OWNER")
        self.assertEqual(gate["verified_buyers"],0)
        self.assertEqual(gate["verified_open_supplier_contracts"],0)

    def test_sector_priority_industrial_precedes_residential(self):
        industrial="26107153ESC23SA"
        residential="22217053NNY17OZ"
        self.saved(residential,"690 SHEPPARD AVE E",{},
                   [self.official(residential,address="690 SHEPPARD AVE E",
                                  description="705 residential units")])
        self.saved(industrial,"2250 MARKHAM RD",{},
                   [self.official(industrial,address="2250 MARKHAM RD",
                                  description="Warehouse industrial expansion")])
        r=build(self.root)
        self.assertTrue(r["projects"][0]["project_id"].endswith(industrial))
        self.assertEqual(r["verified_open_supplier_packages"],0)


if __name__ == "__main__":
    unittest.main()
