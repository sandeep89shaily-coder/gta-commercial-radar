import sqlite3, unittest
from toronto_public_records import setup, persist, SPECS
from toronto_signals import extract, signal, categories

class TorontoSignalsTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:')
  setup(self.db)
  self.source=next(s for s in SPECS if s['id']=='toronto_open_solicitations')
  self.meta={'package_id':'p','resource_id':'r','source_url':'https://open.toronto.ca/dataset/tobids-all-open-solicitations/',
             'resource_url':'https://toronto.example/resource.csv'}
 def tearDown(self):self.db.close()
 def test_initial_snapshot_not_mistaken_for_fresh_opportunity(self):
  persist(self.db,self.source,[{'CALL_NUMBER':'A1','DESCRIPTION':'HVAC replacement'}],self.meta,'day1')
  self.assertEqual(extract(self.db),[])
 def test_post_baseline_change_has_provenance_and_caveat(self):
  persist(self.db,self.source,[{'CALL_NUMBER':'A1','DESCRIPTION':'HVAC replacement'}],self.meta,'day1')
  persist(self.db,self.source,[{'CALL_NUMBER':'A1','DESCRIPTION':'HVAC replacement'},
                               {'CALL_NUMBER':'A2','DESCRIPTION':'CCTV security system installation',
                                'CLOSING_DATE':'2026-11-20','CLIENT_DIVISION':'Facilities'}],self.meta,'day2')
  events=extract(self.db)
  self.assertEqual(len(events),1)
  row=events[0]
  self.assertEqual(row['source_change'],'DATASET_ROW_FIRST_SEEN')
  self.assertEqual(row['signal_type'],'SOLICITATION_RECORD_CHANGE')
  self.assertIn('SECURITY',row['relevant_provider_categories'])
  self.assertEqual(row['published_date'],'2026-11-20')
  self.assertEqual(row['qualification'],'REQUIRES_INDEPENDENT_REVIEW')
  self.assertIn('open.toronto.ca/',row['source_url'])
 def test_noncompetitive_award_is_not_open_tender(self):
  change={'source_id':'toronto_noncompetitive_contracts','observed_at':'now',
          'record_key':'1','change_type':'DATASET_ROW_UPDATED','source_url':'https://open.toronto.ca/'}
  row=signal(change,{'VENDOR_NAME':'Known Supplier','DESCRIPTION':'HVAC maintenance',
                     'CONTRACT_AMOUNT':'12000','DATE_AWARDED':'2026-10-10'})
  self.assertIn('AWARD',row['signal_type'])
  self.assertIn('past purchasing',row['notes'])
  self.assertEqual(row['published_value'],'12000')
 def test_council_schedule_not_a_commercial_signal(self):
  self.assertIsNone(signal({'source_id':'toronto_council_meeting_schedule'},
                           {'TITLE':'Council meeting'}))
 def test_classification_is_explicitly_heuristic(self):
  self.assertEqual(categories('general municipal operations'),'UNCLASSIFIED')
  self.assertEqual(categories('Cooling plant and electrical upgrade'),'HVAC;ELECTRICAL')
if __name__=='__main__':unittest.main()
