import json,tempfile,unittest
from pathlib import Path
from gta_unified_intelligence import build
class UnifiedIntelligenceTests(unittest.TestCase):
 def test_exact_identity_graph_and_unverified_roles(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);review=root/"reviews";review.mkdir()
   project={"project_id":"mississauga:BP 3ALT 26-2522","address":"3899 Trelawny",
            "source_url":"https://services6.arcgis.com/a",
            "sources":[{"url":"https://services6.arcgis.com/a",
              "text":"BP 3ALT 26-2522 Developer Example Holdings",
              "page_identity":"EXACT_CURRENT_PERMIT_ID_IN_PAGE"}],
            "model_suggestions":{"developer":"Example Holdings","operator":"Unknown Business"}}
   (review/"AI_PROJECT_1234567890abcdef.json").write_text(json.dumps(project))
   result=build(root,review)
   self.assertEqual(result["exact_id_project_dossiers"],1)
   self.assertEqual(result["verified_private_leads"],0)
   graph=json.loads((review/"GTA_RADAR_INTELLIGENCE_GRAPH.json").read_text())
   self.assertTrue(any(n["kind"]=="organization" for n in graph["nodes"]))
   self.assertTrue(any(e["verification"]=="AI_HYPOTHESIS" for e in graph["edges"]))
   self.assertFalse(graph["projects"][0]["buyer_authority_verified"])
if __name__=="__main__":unittest.main()
