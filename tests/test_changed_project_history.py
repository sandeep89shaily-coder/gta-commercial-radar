import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import gta_execute_ai_project_research as m
class PreserveHistoryTests(unittest.TestCase):
 def test_changed_project_keeps_earlier_dossier(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);out=root/"review";out.mkdir()
   old=out/("AI_PROJECT_"+__import__("hashlib").sha256(b"project-1").hexdigest()[:16]+".json")
   old.write_text('{"input_hash":"old"}')
   project={"project_id":"project-1","address":"1 Main St","source_id":"A","source_keys":"x","record_source_url":"https://example.org/a","description":"new"}
   with patch.object(m,"locate_candidates",return_value=(root/"queue.csv",[project])),patch.object(m.v5,"key_from_windows",return_value=""):
    result=m.execute(None,root,out,paid=True)
   self.assertEqual(old.read_text(),'{"input_hash":"old"}')
   self.assertEqual(result["status"],"MISSING_API_KEY")
if __name__=="__main__":unittest.main()
