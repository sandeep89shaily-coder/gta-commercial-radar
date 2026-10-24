"""Real IESO 2026 JSON shape, not a fictional HTML table."""
import unittest
import early_cue_watch as cue

def item(cid=3077,code="2026-EX1329",name="New switch installation on D3K"):
 return {"Queue":"","Applicant":"HYDRO ONE NETWORKS INC.","Name":name,
  "CaaId":cid,"CaaIdAndDate":code,"Location":"Northeast",
  "Type":"Station Re-configuration","Size":"-",
  "ProposedInServiceDate":"2026-Q4<br>","SiaStatus":"Active",
  "ReportLinks":"Active<br/>","Committed":""}

class Tests(unittest.TestCase):
 def test_official_json_columns_and_no_date_confusion(self):
  rows=[item(i, f"2026-EX{i}") for i in range(100,160)]
  parsed,warning=cue.parse_ieso_json(rows)
  self.assertEqual(len(parsed),60)
  self.assertEqual(parsed[0]["record_id"],"2026-EX100")
  self.assertEqual(parsed[0]["source_date"],"")
  self.assertEqual(parsed[0]["procurement_status"],"UNKNOWN")
  self.assertEqual(parsed[0]["attributes"]["proposed_service"],"2026-Q4")
  self.assertIn("PUBLISHED_JSON",warning)
 def test_duplicate_ids_never_silently_merge(self):
  with self.assertRaisesRegex(RuntimeError,"Duplicate"):
   cue.parse_ieso_json([item(i,f"2026-EX{i}") for i in range(100,160)]+[item(3077,"2026-EX100")])
 def test_js_missing_html_table_no_longer_required(self):
  # The new source path does not call parse_ieso(html).
  self.assertEqual(cue.IESO_JSON,
   "https://www.ieso.ca/-/media/files/IESO/files/applicationstatusdata.json")

if __name__=="__main__":unittest.main()
