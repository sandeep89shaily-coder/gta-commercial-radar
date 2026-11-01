"""End-to-end data-lineage acceptance: research -> source verify -> buyer worklist.

No network, DeepSeek or fixture-created sales-ready claims.
"""
import csv,json,tempfile,unittest
from pathlib import Path
import gta_live_procurement_evidence as live
import gta_buyer_procurement_batch as batch
from gta_buyer_verification_worklist import build as build_worklist

URL="https://www.toronto.ca/verified-project-123"
QUOTE="Example Corporation plans a new warehouse and will evaluate mechanical contractors."
PID="toronto:123"

def write_csv(path,rows):
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

class BuyerLineageIntegrationTests(unittest.TestCase):
    def setup_records(self,root,ambiguous=False):
        review=root/"TOTAL_INTELLIGENCE_REVIEW"
        review.mkdir()
        (review/"AI_PROJECT_2026110100000000.json").write_text(json.dumps({
            "project_id":PID,"sources":[{"url":URL,"page_identity":"EXACT_CURRENT_PERMIT_ID_IN_PAGE",
                 "text":QUOTE}]}))
        if ambiguous:
            (review/"AI_PROJECT_2026110100000001.json").write_text(json.dumps({
                "project_id":"toronto:456","sources":[{"url":URL}]}))
        (review/"BUYER_RELATIONSHIPS_REVIEW.json").write_text(json.dumps({
            "observations":[{"organization":"Example Corporation","role":"owner",
                             "source_url":URL,"exact_quote":QUOTE}]}))
        write_csv(root/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv",[{
            "project_id":PID,"address":"123 Example Road",
            "opportunity_strength":"IDENTIFIED_PROJECT_OPERATOR",
            "operator":"Example Corporation",
            "description":"New industrial warehouse manufacturing expansion and contractor requirements",
            "record_source_url":URL}])
        return review

    def test_real_legacy_observation_reaches_correct_project_not_sale_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);review=self.setup_records(root)
            rows=live.source_rows(root,review)
            self.assertEqual(rows[0]["project_id"],PID)
            self.assertEqual(rows[0]["lineage"],"UNIQUE_EXACT_SOURCE_URL_RECONCILIATION")
            seen=[]
            def fetch(url):
                seen.append(url)
                return {"ok":True,"url":url,"text":QUOTE,
                        "sha256":"a"*64,"fetched_at":"2026-11-01"}
            report=live.execute(None,review,review=review,results=root,fetcher=fetch)
            self.assertEqual(seen,[URL])
            self.assertEqual(report["records_checked"],1)
            self.assertEqual(report["source_text_matches"],1)
            self.assertEqual(report["verified_buying_authorities"],0)
            self.assertEqual(report["verified_unawarded_packages"],0)
            result=batch.evaluate(root,review,top=10)
            self.assertEqual(result["projects_checked"],1)
            self.assertEqual(result["records"][0]["live_sourced_observations"],1)
            self.assertEqual(result["sale_ready"],0)
            build_worklist(review)
            with (review/"BUYER_VERIFICATION_WORKLIST.csv").open(encoding="utf-8-sig") as stream:
                work=list(csv.DictReader(stream))
            self.assertEqual(work[0]["project_id"],PID)

    def test_shared_url_does_not_invent_a_project_link(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);review=self.setup_records(root,ambiguous=True)
            rows=live.source_rows(root,review)
            self.assertEqual(rows[0]["project_id"],"")
            self.assertEqual(rows[0]["lineage"],"AMBIGUOUS_SOURCE_URL_PROJECT")
            def cannot_fetch(url):
                self.fail("Unlinked evidence must not be fetched as project proof")
            audit=live.execute(None,review,review=review,results=root,fetcher=cannot_fetch)
            self.assertEqual(audit["unlinked_observations"],1)
            self.assertEqual(audit["records"][0]["reason"],"AMBIGUOUS_SOURCE_URL_PROJECT")
            self.assertEqual(audit["source_text_matches"],0)
            build_worklist(review)
            with (review/"BUYER_VERIFICATION_WORKLIST.csv").open(encoding="utf-8-sig") as stream:
                work=list(csv.DictReader(stream))
            self.assertEqual(work[0]["project_id"],"")

    def test_buyer_worklist_rejects_address_as_company(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);review=self.setup_records(root)
            source=review/"BUYER_RELATIONSHIPS_REVIEW.json"
            obs=json.loads(source.read_text())
            obs["observations"].append({
                "organization":"318 Example Rd, Brampton, ON","role":"owner",
                "source_url":"https://maps1.brampton.ca/arcgis/query",
                "exact_quote":"ADDRESS 318 Example Rd, Brampton, ON",
                "project_id":"brampton:99"})
            source.write_text(json.dumps(obs))
            result=build_worklist(review)
            self.assertEqual(result["total_sourced_observations"],2)
            self.assertEqual(result["rejected_invalid_organizations"],1)
            self.assertEqual(result["candidates_for_human_or_official_source_verification"],1)
            with (review/"BUYER_VERIFICATION_WORKLIST.csv").open(encoding="utf-8-sig") as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(rows[1]["organization_quality_status"],"REJECTED_INVALID_ORGANIZATION")

if __name__=="__main__":
    unittest.main()
