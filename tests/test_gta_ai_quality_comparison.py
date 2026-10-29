import json,tempfile,unittest
from pathlib import Path
from gta_ai_quality_comparison import compare
class QualityComparisonTests(unittest.TestCase):
 def test_only_compares_same_actual_project(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder); before=root/"before";after=root/"after";before.mkdir();after.mkdir()
   record={"project_id":"T-A","sources":[],"model_suggestions":{"developer":""},"sale_ready":False}
   (before/"AI_PROJECT_1234567890abcdef.json").write_text(json.dumps(record))
   updated={**record,"sources":[{"page_identity":"EXACT_CURRENT_PERMIT_ID_IN_PAGE","text":"record"}],
          "model_suggestions":{"developer":"Example"}}
   (after/"AI_PROJECT_1234567890abcdef.json").write_text(json.dumps(updated))
   result=compare(before,after)
   self.assertEqual(result["shared_projects"],1)
   self.assertEqual(result["comparisons"][0]["before"]["pages"],0)
   self.assertEqual(result["comparisons"][0]["after"]["specific_source_pages"],1)
   self.assertFalse(result["comparisons"][0]["after"]["sale_ready"])
if __name__=="__main__":unittest.main()
