import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gta_execute_ai_project_research import read_candidates,execute
class ExecuteAITests(unittest.TestCase):
 def sample(self,path):
  with path.open("w",newline="",encoding="utf-8") as h:
   w=csv.DictWriter(h,fieldnames=["project_id","address","source_id","source_keys","record_source_url","description"])
   w.writeheader()
   w.writerow({"project_id":"B-1","address":"175 Oak Street",
    "source_id":"toronto","source_keys":"A123","record_source_url":"https://www.toronto.ca/planning","description":"Warehouse"})
 def test_no_paid_call_without_optin(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/"candidate.csv";self.sample(p)
   with patch("gta_execute_ai_project_research.native.fetch_native") as f:
    status=execute(p,root,root/"review")
    self.assertEqual(status["attempted"],0)
    f.assert_not_called()
 def test_real_native_research_writes_review_with_mock_transport(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/"candidate.csv";self.sample(p)
   with patch("gta_execute_ai_project_research.native.fetch_native",return_value=([{"url":"https://www.toronto.ca/planning","text":"Warehouse plan"}],{"search":1,"fetch":1})),patch("gta_execute_ai_project_research.native.analyze",return_value=({"owner":"Example Corp"},0.001)) as analyze:
    status=execute(p,root,root/"review",paid=True,key="mock")
   self.assertEqual(status["completed"],1)
   payloads=list((root/"review").glob("AI_PROJECT_*.json"))
   self.assertEqual(len(payloads),1)
   saved=json.loads(payloads[0].read_text())
   self.assertFalse(saved["sale_ready"])
   self.assertEqual(saved["model_suggestions"]["owner"],"Example Corp")
   analyze.assert_called_once()
if __name__=="__main__":unittest.main()
