import unittest, json, pathlib
class ExpandedSourceTests(unittest.TestCase):
 def test_expanded_sources_have_safe_disabled_defaults(self):
  s=json.loads((pathlib.Path(__file__).resolve().parents[1]/'config/sources.json').read_text())
  d={x['id']:x for x in s}
  for k in ['hamilton_building_demolition_permits','kitchener_active_planning_applications']:
   self.assertIn(k,d)
   self.assertFalse(d[k]['enabled'])
   self.assertEqual('arcgis',d[k]['collector'])
   self.assertTrue(d[k]['key_fields'])
   self.assertTrue(d[k]['query_url'].startswith('https://'))
 def test_no_federal_sources(self):
  s=json.loads((pathlib.Path(__file__).resolve().parents[1]/'config/sources.json').read_text())
  self.assertFalse(any('canadabuys' in x['id'] for x in s))
