import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import gta_manual_project_list as listing
import gta_discovery_run as discovery
import gta_total_intelligence_run as full

def csv_write(path,rows):
    with path.open("w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

class DiscoveryManualHandoffTests(unittest.TestCase):
    def seed(self,root):
        csv_write(root/listing.SOURCE,[{
            "project_id":"toronto:1","observation":"FIRST_OBSERVED",
            "city":"Toronto","address":"10 Example Ave",
            "description":"New warehouse proposal 20000 sq ft",
            "source_record_date":"2026-11-01",
            "first_seen_local":"2026-11-01",
            "current_source_status":"PRE_APPROVAL",
            "record_source_url":"https://www.toronto.ca/example",
        },{
            "project_id":"toronto:2","observation":"RECORD_CHANGED",
            "city":"Toronto","address":"20 Sample Rd",
            "description":"Factory expansion",
            "record_source_url":"https://www.toronto.ca/other",
        }])
        csv_write(root/listing.AI_SOURCE,[{
            "project_id":"toronto:1","investigated_local_date":"2026-11-01",
            "api_attempted":"YES","status":"AI_EVIDENCE_REVIEW",
            "native_searches":"3","project_stage":"planning",
            "source_urls":"https://www.toronto.ca/example",
            "operator":"Example Co","related_company":"",
            "contact":"info@example.com",
            "contact_source_url":"https://example.com/contact",
            "related_company_contact":"","related_company_contact_url":"",
        },{
            "project_id":"toronto:2","investigated_local_date":"2026-10-28",
            "api_attempted":"YES","status":"AI_EVIDENCE_REVIEW",
            "native_searches":"5","project_stage":"construction",
            "source_urls":"https://www.toronto.ca/other",
            "operator":"Stale Co","related_company":"",
            "contact":"stale@example.com",
            "contact_source_url":"https://example.com/contact",
            "related_company_contact":"","related_company_contact_url":"",
        }])
    def test_initial_deepseek_public_contact_hints_preserved_without_buyer_claims(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root)
            report=listing.build(root,today=__import__("datetime").date(2026,11,1))
            self.assertEqual(report["new_or_changed_source_records"],2)
            self.assertEqual(report["initial_public_contact_hints"],1)
            self.assertEqual(report["verified_buyers_claimed"],0)
            self.assertEqual(report["supplier_packages_claimed"],0)
            with Path(report["manual_review_csv"]).open(encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(rows[0]["public_business_contact_hint_unverified"],"info@example.com")
            self.assertEqual(rows[0]["public_contact_source_url"],"https://example.com/contact")
            self.assertEqual(rows[1]["deepseek_initial_status"],"NOT_QUERIED_THIS_RUN")
            self.assertEqual(rows[1]["public_business_contact_hint_unverified"],"")
            html=Path(report["manual_review_html"]).read_text(encoding="utf-8")
            self.assertIn("info@example.com",html)
            self.assertIn("Public business contact source",html)
            report2=listing.build(root,today=__import__("datetime").date(2026,11,1))
            self.assertNotEqual(report["manual_review_csv"],report2["manual_review_csv"])
            self.assertTrue(Path(report["manual_review_csv"]).exists())

    def test_default_runner_selective_deepseek_including_contacts_and_no_buyer_jobs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            called=[]
            class Result:
                returncode=0
            def fake(cmd,**kwargs):
                called.append(cmd)
                self.seed(root/"GTA_RADAR_RESULTS")
                (root/"GTA_RADAR_RESULTS"/"GTA_RADAR_V6_RUN.json").write_text(json.dumps({
                    "status":"SUCCESS","selective_ai":{"paid_research_attempts":1,
                    "company_contact_searches":1,"daily_ceiling_usd":0.25}}))
                return Result()
            def ok(*args,**kwargs):return {"ok":True,"status":"OK_UP_TO_DATE","installed_commit":"abc"}
            rc=discovery.execute(root,runner=fake,preflight=ok)
            self.assertEqual(rc,0)
            self.assertEqual(len(called),1)
            self.assertIn("--selective-ai",called[0])
            self.assertNotIn("--no-ai",called[0])
            self.assertNotIn("gta_integrated_buyer_investigation.py"," ".join(called[0]))
            out=json.loads((root/"GTA_RADAR_RESULTS"/"GTA_RADAR_DISCOVERY_RUN_STATUS.json").read_text())
            self.assertTrue(out["completed"])
            self.assertEqual(out["initial_deepseek"]["company_contact_searches"],1)
            self.assertFalse(out["supplier_or_procurement_investigation_automated"])

    def test_existing_full_command_defaults_to_discovery(self):
        with patch("gta_discovery_run.execute",return_value=0) as mocked:
            self.assertEqual(full.execute("/a/test/workspace"),0)
            mocked.assert_called_once_with("/a/test/workspace")
if __name__=="__main__":
    unittest.main()
