import csv,json,tempfile,unittest
from pathlib import Path
from gta_release_acceptance import acceptance
from gta_discovery_tracking import track
class ReleaseIntegrationTests(unittest.TestCase):
 def test_release_rejects_unverified_buyer(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   (root/"AI_PROJECT_0123456789abcdef.json").write_text(json.dumps({
     "project_id":"P1","address":"69 First Gulf Blvd","sources":[{"url":"https://maps1.brampton.ca/",
     "page_identity":"EXACT_CURRENT_PERMIT_ID_IN_PAGE"}],"model_suggestions":{"developer":"Example"}}))
   result=acceptance(root)
   self.assertEqual(result["official_exact_id_projects"],1)
   self.assertEqual(result["sale_ready"],0)
   self.assertFalse(result["production_acceptance"])
 def test_first_seen_persists_without_false_leadtime(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);q=root/"queue.csv"
   with q.open("w",newline="") as out:
    w=csv.DictWriter(out,fieldnames=["project_id","record_source_url"]);w.writeheader()
    w.writerow({"project_id":"P1","record_source_url":"https://toronto.ca/a"})
   self.assertEqual(track(q,root)["measurable"],0)
   self.assertEqual(track(q,root)["total"],1)
if __name__=="__main__":unittest.main()
