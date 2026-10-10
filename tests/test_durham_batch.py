import json,unittest
from pathlib import Path
class DurhamBatchTest(unittest.TestCase):
 def test_all_new_disabled_and_configured(self):
  src=json.loads((Path(__file__).parents[1]/'config/sources.json').read_text())
  wanted={'durham_planit_consents','durham_planit_opa','durham_business_sites','durham_capital_projects'}
  found={x['id']:x for x in src if x['id'] in wanted}
  self.assertEqual(set(found),wanted)
  for a in found.values():
   self.assertFalse(a['enabled'])
   self.assertEqual(a['collector'],'arcgis')
   self.assertTrue(a['query_url'].endswith('/query'))
   self.assertEqual(a['mode'],'monthly')
 def test_no_duplicate_ids(self):
  src=json.loads((Path(__file__).parents[1]/'config/sources.json').read_text())
  self.assertEqual(len(src),len({x['id'] for x in src}))
