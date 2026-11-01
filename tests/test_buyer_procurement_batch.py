import csv,tempfile,unittest,json
from pathlib import Path
import gta_buyer_procurement_batch as batch

class BuyerProcurementBatchTests(unittest.TestCase):
 def test_no_source_file_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   r=batch.evaluate(p,p,top=10)
   self.assertEqual(r["projects_checked"],0)
   self.assertEqual(r["sale_ready"],0)
   self.assertEqual(r["verified_open_packages"],0)
 def test_ten_records_never_mark_ai_names_as_verified(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   path=p/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv"
   rows=[{"project_id":f"toronto:{i:04d}","address":f"{i} Sample Rd",
       "operator":"Unverified Operator","opportunity_strength":"IDENTIFIED_PROJECT_OPERATOR",
       "description":"New commercial industrial warehouse expansion, 20000 sq ft",
       "record_source_url":f"https://www.toronto.ca/record/{i}"} for i in range(13)]
   with path.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
   result=batch.evaluate(p,p,top=10)
   self.assertEqual(result["projects_checked"],10)
   self.assertEqual(result["verified_buyers"],0)
   self.assertEqual(result["verified_open_packages"],0)
   self.assertEqual(result["sale_ready"],0)
   self.assertTrue(all(x["operator_status"]=="UNVERIFIED_HINT" for x in result["records"]))
   self.assertTrue(all(x["supplier_status"]=="UNKNOWN" for x in result["records"]))
   prefix=batch.write(result,p/"out")
   self.assertTrue(Path(prefix+".csv").exists())
   self.assertTrue(Path(prefix+".json").exists())
 def test_live_quote_is_review_queue_only_never_supplier_confirmation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   rows=[{"project_id":"toronto:12345","address":"100 Sample Rd","operator":"Suggested Co",
       "opportunity_strength":"IDENTIFIED_PROJECT_OPERATOR",
       "description":"New industrial warehouse with mechanical equipment expansion",
       "record_source_url":"https://www.toronto.ca/record/12345"}]
   with (p/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
   report={"records":[{"project_id":"toronto:12345","proof_status":"SOURCE_TEXT_MATCHED","kind":"PROCUREMENT_PACKAGE"}]}
   (p/"LIVE_PROCUREMENT_EVIDENCE_20261101T150000.json").write_text(json.dumps(report))
   result=batch.evaluate(p,p,top=10)
   self.assertEqual(result["records"][0]["live_sourced_observations"],1)
   self.assertEqual(result["records"][0]["next_action"],"HUMAN_REVIEW_MATCHED_PURCHASING_EVIDENCE")
   self.assertEqual(result["verified_open_packages"],0)
   self.assertEqual(result["verified_buyers"],0)
   self.assertEqual(result["sale_ready"],0)
 def test_actual_ai_research_cohort_prioritized_over_unrelated_operator_hints(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);review=root/"review";review.mkdir()
   with (root/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv").open("w",newline="") as f:
    r=[{"project_id":"operator:old","address":"1 Old Rd","operator":"Hint LLC",
        "opportunity_strength":"IDENTIFIED_PROJECT_OPERATOR",
        "description":"Industrial warehouse expansion 25000 sq ft",
        "record_source_url":"https://www.toronto.ca/old"}]
    w=csv.DictWriter(f,fieldnames=r[0].keys());w.writeheader();w.writerows(r)
   with (root/"GTA_RADAR_V8_PENDING_QUEUE.csv").open("w",newline="") as f:
    r=[{"project_id":"toronto_development_applications:20198309STE13SA",
        "address":"166 DUNDAS ST E","operator":"","record_source_url":"https://www.toronto.ca/new"}]
    w=csv.DictWriter(f,fieldnames=r[0].keys());w.writeheader();w.writerows(r)
   (review/"AI_PROJECT_RESEARCH_MANIFEST.json").write_text(json.dumps({
     "audit":[{"project_id":"toronto_development_applications:20198309STE13SA",
               "status":"AI_REVIEW_SAVED","selection_score":93},
              {"project_id":"already:reviewed","status":"ALREADY_REVIEWED"}],
     "selection":{"top":[{"project_id":"toronto_development_applications:20198309STE13SA",
                             "address":"166 DUNDAS ST E","score":93}]}}))
   chosen=batch.choose(root,top=1,review=review)
   self.assertEqual(len(chosen),1)
   self.assertEqual(chosen[0]["project_id"],"toronto_development_applications:20198309STE13SA")
   self.assertEqual(chosen[0]["selection_basis"],"CURRENT_AI_PROJECT_RESEARCH_AUDIT")
   out=batch.evaluate(root,review,top=1)
   self.assertEqual(out["recent_ai_researched_projects_selected"],1)
   self.assertEqual(out["verified_buyers"],0)
   self.assertEqual(out["verified_open_packages"],0)
   self.assertEqual(out["sale_ready"],0)
 def test_no_recent_research_keeps_existing_operator_fallback(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);review=root/"review";review.mkdir()
   (review/"AI_PROJECT_RESEARCH_MANIFEST.json").write_text(json.dumps({
     "audit":[{"project_id":"a","status":"ALREADY_REVIEWED"}]}))
   with (root/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv").open("w",newline="") as f:
    r=[{"project_id":"operator:one","address":"20 Industrial Road",
        "operator":"Sample LLC","opportunity_strength":"IDENTIFIED_PROJECT_OPERATOR",
        "description":"New industrial warehouse 20000 sq ft","record_source_url":"https://www.toronto.ca/one"}]
    w=csv.DictWriter(f,fieldnames=r[0].keys());w.writeheader();w.writerows(r)
   result=batch.evaluate(root,review,top=1)
   self.assertEqual(result["recent_ai_researched_projects_selected"],0)
   self.assertEqual(result["projects_checked"],1)
if __name__=="__main__":unittest.main()
