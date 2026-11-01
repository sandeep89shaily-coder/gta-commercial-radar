import csv,json,tempfile,unittest
from pathlib import Path
import gta_source_evidence_intake as intake
import reviewed_evidence as evidence

class EvidenceIntakeTests(unittest.TestCase):
 def write(self,path,rows):
  with path.open("w",newline="",encoding="utf-8") as h:
   w=csv.DictWriter(h,fieldnames=sorted({k for row in rows for k in row}))
   w.writeheader();w.writerows(rows)
 def test_recover_from_existing_source_and_never_promote_ai(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   self.write(root/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv",[{
      "project_id":"city:123","address":"100 Factory Rd","opportunity_strength":"IDENTIFIED_PROJECT_OPERATOR",
      "operator":"Example Foods","record_source_url":"https://www.toronto.ca/permit/123","description":""}])
   self.write(root/"GTA_RADAR_V8_PENDING_QUEUE.csv",[{
      "project_id":"city:123","address":"100 Factory Rd","description":"New commercial manufacturing plant expansion with refrigeration",
      "record_source_url":"https://www.toronto.ca/permit/123"}])
   summary=intake.run(root,root/"output",top=10)
   self.assertEqual(summary["claim_specs"],1)
   self.assertEqual(summary["verified_claims"],0)
   self.assertFalse((root/"AUTO_VERIFIED_EVIDENCE.json").exists())
   self.assertFalse((root/"REVIEWED_EVIDENCE.json").exists())
   data=json.loads(next((root/"output").glob("SOURCE_INTAKE_*.json")).read_text())
   self.assertEqual(data["specs"][0]["claims"]["scope_evidence"]["excerpt"],
                    "New commercial manufacturing plant expansion with refrigeration")
 def test_fail_closed_when_source_does_not_contain_quote(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   self.write(root/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv",[{
      "project_id":"city:124","address":"200 Factory Rd","opportunity_strength":"IDENTIFIED_PROJECT_OPERATOR",
      "operator":"Example Foods","record_source_url":"https://www.toronto.ca/permit/124",
      "description":"Large manufacturing plant expansion with refrigerated warehouse"}])
   def fake(url):
    return {"ok":True,"url":url,"text":"unrelated public content","sha256":"a"*64,"fetched_at":"2026-11-01"}
   result=intake.run(root,root/"output",fetcher=fake)
   self.assertEqual(result["verified_claims"],0)
   gate=evidence.evaluate_folder(root)
   self.assertFalse(next(iter(gate["results"].values()))["sale_ready"])
if __name__=="__main__":unittest.main()
