import tempfile
import unittest
from pathlib import Path
from commercial_engine import normalize_address,group_opportunities,write_opportunity_outputs

class CommercialEngineTests(unittest.TestCase):
    def test_unit_is_not_stripped(self):
        self.assertNotEqual(normalize_address('100 Main St Unit 5'),normalize_address('100 Main St Unit 6'))
    def test_two_sources_one_address_multiple_buyers(self):
        base={'change_type':'NEW','address':'100 Main St Unit 5','jurisdiction':'Toronto','commercial_relevance':'HIGH','observed_at':'2026-10-09'}
        rows=group_opportunities([{**base,'source_id':'permits','record_key':'1','description':'New restaurant'},
                                  {**base,'source_id':'licences','record_key':'2','description':'Restaurant business licence'}])
        self.assertEqual(len(set(r['opportunity_id'] for r in rows)),1)
        self.assertTrue(all(r['source_count']==2 for r in rows))
        self.assertTrue(all(r['review_status']=='UNVERIFIED_NOT_FOR_SALE' for r in rows))
        self.assertGreaterEqual(len(set(r['buyer_category'] for r in rows)),3)
    def test_different_cities_never_merge(self):
        base={'change_type':'NEW','address':'1 Queen St','description':'New retail store'}
        rows=group_opportunities([{**base,'jurisdiction':'Toronto'},{**base,'jurisdiction':'Brampton'}])
        self.assertEqual(len(set(r['opportunity_id'] for r in rows)),2)
    def test_skips_older_baseline_and_missing_address(self):
        self.assertEqual(group_opportunities([{'change_type':'BASELINE','address':'1 St','description':'Restaurant'},
                                              {'change_type':'NEW','description':'Restaurant'}]),[])
    def test_writes_empty_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(write_opportunity_outputs(d,[]),(0,0))
            self.assertTrue((Path(d)/'opportunities_REVIEW_ONLY.csv').exists())
            self.assertTrue((Path(d)/'buyer_leads_REVIEW_ONLY'/'commercial_insurance.csv').exists())
