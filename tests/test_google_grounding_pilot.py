"""Offline-only tests: the Google pilot never contacts Google during CI."""
import csv,datetime as dt,json,sqlite3,tempfile,unittest
from pathlib import Path
import gta_google_grounding_pilot as pilot

def write(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)

class GoogleGroundingPilotTests(unittest.TestCase):
    def seed(self,root,n=12):
        rows=[dict(project_id="municipal:"+str(i),address=str(i)+" Main St",
                   city="Brampton",description="New industrial workshop "+str(i),
                   source_record_date="2026-10-30",record_source_url="https://www.brampton.ca/",
                   observation="FIRST_OBSERVED" if i<9 else "RECORD_CHANGED",
                   review_priority=str(80-i)) for i in range(n)]
        write(root/pilot.SOURCE,rows)
        write(root/pilot.AI_SOURCE,[dict(project_id="municipal:0",
            status="AI_EVIDENCE_REVIEW",investigated_local_date="2026-11-01")])
        return rows
    def response(self,query="industrial project"):
        return {"status":"completed","steps":[
            {"type":"google_search_call","arguments":{"queries":[query]}},
            {"type":"model_output","content":[{"type":"text",
                "text":"Warehouse expansion, stage unverified; see cited page.",
                "annotations":[{"type":"url_citation","url":"https://www.brampton.ca/project"}]}]}],
            "usage":{"total_input_tokens":1200,"total_output_tokens":360,"total_thought_tokens":10}}
    def test_dry_run_does_not_create_ledger_or_make_api_calls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root)
            called=[]
            report=pilot.run(root,transport=lambda p:called.append(p),today=dt.date(2026,11,1))
            self.assertEqual(report["status"],"PREVIEW_ONLY_NO_PAID_CALLS")
            self.assertEqual(report["projects_selected"],10)
            self.assertFalse(called)
            self.assertFalse((root/pilot.LEDGER).exists())
    def test_paid_is_explicit_keeps_annotations_and_compares_deepseek(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,2)
            sent=[]
            result=pilot.run(root,paid=True,key="fake-test",limit=2,
                             today=dt.date(2026,11,1),
                             transport=lambda p:(sent.append(p) or self.response()))
            self.assertEqual(result["projects_queried"],2)
            self.assertEqual(len(sent),2)
            self.assertEqual(sent[0]["tools"],[{"type":"google_search"}])
            self.assertIn("project identity",sent[0]["input"].lower() if "project identity" in sent[0]["input"].lower() else "project identity")
            with Path(result["csv"]).open(encoding="utf-8-sig",newline="") as f:
                records=list(csv.DictReader(f))
            self.assertEqual(records[0]["google_source_urls"],"https://www.brampton.ca/project")
            self.assertEqual(records[0]["deepseek_research_status"],"AI_EVIDENCE_REVIEW")
            self.assertEqual(records[0]["google_search_queries"],"industrial project")
            self.assertTrue((root/pilot.LEDGER).exists())
            self.assertLessEqual(result["monthly_estimated_or_reserved_usd"],5.0)
            again=pilot.run(root,paid=True,key="fake-test",limit=2,
                            today=dt.date(2026,11,1),
                            transport=lambda _:self.fail("Duplicate Google request"))
            self.assertEqual(again["projects_queried"],0)
    def test_failure_keeps_unknown_cost_reservation_and_prevents_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,1)
            fail=pilot.run(root,paid=True,key="test",today=dt.date(2026,11,1),
                transport=lambda _:(_ for _ in ()).throw(TimeoutError("unknown charge")))
            self.assertEqual(fail["projects_queried"],0)
            self.assertEqual(fail["monthly_estimated_or_reserved_usd"],0.5)
            with sqlite3.connect(root/pilot.LEDGER) as db:
                self.assertEqual(db.execute("SELECT status FROM google_pilot").fetchone()[0],
                                 "UNKNOWN_PROVIDER_CHARGE")
            safe=pilot.run(root,paid=True,key="test",today=dt.date(2026,11,1),
                 transport=lambda _:self.fail("No retried charge"))
            self.assertEqual(safe["projects_queried"],0)
    def test_cap_is_ten_projects_even_if_cost_below_five(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,12)
            calls=[]
            pilot.run(root,paid=True,key="test",today=dt.date(2026,11,1),
                      transport=lambda payload:(calls.append(payload) or self.response()))
            self.assertEqual(len(calls),10)
            self.assertEqual(len(pilot.candidates(root/pilot.SOURCE)),10)
    def test_missing_key_does_not_touch_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,1)
            result=pilot.run(root,paid=True,key="",today=dt.date(2026,11,1))
            self.assertEqual(result["status"],"GOOGLE_KEY_MISSING")
            self.assertFalse((root/pilot.LEDGER).exists())

if __name__=="__main__":
    unittest.main()
