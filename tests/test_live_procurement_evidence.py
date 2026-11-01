import csv,json,tempfile,unittest
from pathlib import Path
import gta_live_procurement_evidence as live

class PurchasingEvidenceTests(unittest.TestCase):
 def test_real_quote_is_not_equated_to_unawarded_contract(self):
  def fetch(url):return {"ok":True,"url":url,"text":"The company has published a tender for equipment services at its new facility.","fetched_at":"2026-11-01","sha256":"a"*64}
  rows=[{"project_id":"project1","kind":"PROCUREMENT_PACKAGE","source_url":"https://www.brampton.ca/tenders","excerpt":"published a tender for equipment services at its new facility","status":"NOT_AWARDED_AFFIRMATIVE"}]
  r=live.inspect(rows,fetch)
  self.assertEqual(r[0]["proof_status"],"SOURCE_TEXT_MATCHED")
  self.assertFalse(r[0]["unawarded_package_verified"])
  self.assertFalse(r[0]["purchasing_authority_verified"])
 def test_fabricated_quote_and_network_failure_fail_closed(self):
  rows=[{"project_id":"p","kind":"BUYING_AUTHORITY","source_url":"https://www.toronto.ca/projects","excerpt":"Chief procurement officer has approved this current project and all contracts"}]
  wrong=live.inspect(rows,lambda u:{"ok":True,"text":"Unrelated Toronto municipal announcement","url":u})
  self.assertEqual(wrong[0]["proof_status"],"REJECTED")
  blocked=live.inspect(rows,lambda u:{"ok":False,"reason":"ROBOTS_DISALLOWED"})
  self.assertEqual(blocked[0]["proof_status"],"INCONCLUSIVE")
 def test_existing_project_buyer_records_only_with_exact_quotes_and_ids(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);review=root/"review";review.mkdir()
   (review/"BUYER_RELATIONSHIPS_REVIEW.json").write_text(json.dumps({"observations":[
     {"organization":"Company","source_url":"https://www.toronto.ca/x","exact_quote":"Company owns site but award unknown","project_id":"p1"},
     {"organization":"Other","source_url":"https://www.toronto.ca/y","exact_quote":"No project identity"}
   ]}))
   source=live.source_rows(root,review)
   self.assertEqual(len(source),1)
   self.assertEqual(source[0]["project_id"],"p1")
   result=live.execute(None,review,fetcher=lambda u:{"ok":True,"url":u,"text":"Company owns site but award unknown"})
   self.assertEqual(result["verified_buying_authorities"],0)
   self.assertEqual(result["verified_unawarded_packages"],0)
if __name__=="__main__":unittest.main()
