import json, pathlib, unittest

class RegionalExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=json.loads((pathlib.Path(__file__).resolve().parents[1]/'config/sources.json').read_text())
    def test_three_sources_present_disabled(self):
        lookup={s['id']:s for s in self.src}
        for sid in ('hamilton_development_applications','waterloo_city_building_permits','st_catharines_building_permits'):
            self.assertIn(sid,lookup)
            self.assertFalse(lookup[sid]['enabled'])
            self.assertEqual('arcgis',lookup[sid]['collector'])
    def test_no_duplicate_ids(self):
        ids=[s['id'] for s in self.src]
        self.assertEqual(len(ids),len(set(ids)))
    def test_no_federal_feeds(self):
        self.assertFalse(any('canadabuys' in s['id'] for s in self.src))
