import json,tempfile,unittest
from pathlib import Path
from gta_commercial_review_html import build
class CommercialReviewTests(unittest.TestCase):
 def test_generates_html_csv_without_sale_ready_claims(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   (root/"AI_PROJECT_0123456789abcdef.json").write_text(json.dumps({
     "project_id":"permit-1","address":"69 First Gulf Blvd",
     "sources":[{"url":"https://maps1.brampton.ca/a","page_identity":"EXACT_CURRENT_PERMIT_ID_IN_PAGE"}],
     "model_suggestions":{"project_stage":"Ready to Issue","developer":"Hypothesis"}}))
   result=build(root)
   page=result.read_text()
   self.assertIn("69 First Gulf Blvd",page)
   self.assertIn("Supplier availability: unknown",page)
   self.assertIn("not verified",page)
   self.assertTrue((root/"COMMERCIAL_REVIEW.csv").exists())
   self.assertFalse(json.loads((root/"COMMERCIAL_REVIEW.json").read_text())["projects"][0]["sale_ready"])
if __name__=="__main__":unittest.main()
