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
  rows=[{"project_id":"p","kind":"BUYING_AUTHORITY","organization":"Example Corporation","source_url":"https://www.toronto.ca/projects","excerpt":"Chief procurement officer has approved this current project and all contracts"}]
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
   self.assertEqual(len(source),2)
   self.assertEqual(source[1]["lineage"],"MISSING_PROJECT_ID")
   self.assertEqual(source[0]["project_id"],"p1")
   result=live.execute(None,review,review=review,results=root,fetcher=lambda u:{"ok":True,"url":u,"text":"Company owns site but award unknown"})
   self.assertEqual(result["records_checked"],2)
   self.assertEqual(result["unlinked_observations"],1)
   self.assertEqual(result["records"][1]["reason"],"MISSING_PROJECT_ID")
   self.assertEqual(result["verified_buying_authorities"],0)
   self.assertEqual(result["verified_unawarded_packages"],0)
 def test_archive_style_address_is_not_a_buyer_and_valid_tenant_is_only_mention(self):
  rows=[
   {"project_id":"brampton:1","kind":"ORGANIZATION_MENTION","organization":"318 Example Rd, Brampton, ON",
    "source_url":"https://maps1.brampton.ca/arcgis/query",
    "excerpt":"ADDRESS: 318 Example Rd, Brampton, ON"},
   {"project_id":"brampton:3","kind":"ORGANIZATION_MENTION","organization":"1867 INNER CIR",
    "source_url":"https://services6.arcgis.com/issued/permits/query",
    "excerpt":"ADDRESS: 1867 INNER CIR"},
   {"project_id":"toronto:2","kind":"ORGANIZATION_MENTION","organization":"EXAMPLE FOOD SERVICES",
    "source_url":"https://services6.arcgis.com/issued/permits/query",
    "excerpt":"INTERIOR ALTERATIONS - EXAMPLE FOOD SERVICES"},
  ]
  fetched=[]
  def fetch(url):
   fetched.append(url)
   return {"ok":True,"url":url,"text":"INTERIOR ALTERATIONS - EXAMPLE FOOD SERVICES"}
  result=live.inspect(rows,fetch)
  self.assertEqual(result[0]["reason"],"ADDRESS_NOT_ORGANIZATION")
  self.assertFalse(result[0]["source_match"])
  self.assertEqual(fetched,["https://services6.arcgis.com/issued/permits/query"])
  self.assertEqual(result[1]["reason"],"ADDRESS_NOT_ORGANIZATION")
  self.assertTrue(result[2]["source_match"])
  self.assertFalse(result[1]["source_match"])
  self.assertEqual(result[2]["proof_status"],"SOURCE_TEXT_MATCHED")
  self.assertEqual(result[2]["kind"],"ORGANIZATION_MENTION")
  self.assertFalse(result[2]["purchasing_authority_verified"])
if __name__=="__main__":unittest.main()
