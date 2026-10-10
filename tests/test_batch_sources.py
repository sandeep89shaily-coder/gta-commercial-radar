import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
IDS={'mississauga_site_plan_applications','mississauga_rezoning_applications','richmond_hill_active_development_applications'}
class BatchSourceTests(unittest.TestCase):
    def test_three_staged_collectors_and_identity(self):
        src=json.loads((ROOT/'config/sources.json').read_text())
        ids=[s['id'] for s in src]
        self.assertEqual(len(ids),len(set(ids)))
        for s in src:
            if s['id'] in IDS:
                self.assertEqual(s['collector'],'arcgis')
                self.assertFalse(s['enabled'])
                self.assertEqual(s['mode'],'monthly')
                self.assertTrue(s['key_fields'])
                self.assertTrue(s['query_url'].endswith('/query'))
                self.assertEqual(s['validation_state'],'SCHEMA_VERIFIED_LIVE_COLLECTION_NOT_TESTED')
        self.assertEqual(sum(s['id'] in IDS for s in src),3)
    def test_date_field_not_assumed_incremental(self):
        src=json.loads((ROOT/'config/sources.json').read_text())
        for s in src:
            if s['id'] in IDS:
                self.assertNotIn('incremental_fields',s)
