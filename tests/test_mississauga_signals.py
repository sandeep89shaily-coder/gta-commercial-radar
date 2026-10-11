import sqlite3
import tempfile
import unittest
from pathlib import Path
from toronto_public_records import setup,persist
from mississauga_signals import archive_changes,translate,categories

class MississaugaSignalTests(unittest.TestCase):
 def test_source_classification_and_bid_unverified(self):
  change={'source_id':'mississauga_bidsandtenders_legacy','record_key':'PRC005419',
          'observed_at':'2026-10-11T14:00:00Z','change_type':'DATASET_ROW_UPDATED',
          'source_url':'https://mississauga.bidsandtenders.ca/'}
  record={'BID_NUMBER':'PRC005419','TITLE':'Cooling / HVAC service tender',
          'STATUS':'OPEN','DETAIL_URL':'https://mississauga.bidsandtenders.ca/Module/Tenders/en/Tender/Detail/abc'}
  out=translate(change,record)
  self.assertEqual(out['application_or_bid_id'],'PRC005419')
  self.assertIn('HVAC',out['provider_categories'])
  self.assertEqual(out['qualification'],'REQUIRES_INDEPENDENT_REVIEW')
  self.assertIn('verify if opportunity is open',out['notes'])
 def test_unknown_source_never_signal(self):
  self.assertIsNone(translate({'source_id':'caledon'},{}))
 def test_baseline_not_exported_but_updated_application_is(self):
  with tempfile.TemporaryDirectory() as folder:
   database=Path(folder)/'records.sqlite'
   db=sqlite3.connect(database)
   setup(db)
   spec={'id':'mississauga_site_plan_applications','department':'City Planning','keys':('APP_FILE_NO',)}
   meta={'package_id':'city-layer','resource_id':'city-layer',
         'resource_url':'https://services6.arcgis.com/city/FeatureServer/0/query',
         'source_url':'https://services6.arcgis.com/city/FeatureServer/0'}
   persist(db,spec,[{'APP_FILE_NO':'SP100','DESCRIPTION':'Industrial warehouse'}],meta,'day1')
   db.close()
   self.assertEqual(archive_changes(database,{spec['id']}),[])
   db=sqlite3.connect(database)
   persist(db,spec,[{'APP_FILE_NO':'SP100','DESCRIPTION':'Industrial warehouse HVAC retrofit'}],meta,'day2')
   db.close()
   results=archive_changes(database,{spec['id']})
   self.assertEqual(len(results),1)
   self.assertEqual(results[0]['signal_type'],'SITE_PLAN_APPLICATION_CHANGE')
   self.assertEqual(results[0]['qualification'],'REQUIRES_INDEPENDENT_REVIEW')
   self.assertIn('HVAC',results[0]['provider_categories'])
if __name__=='__main__':unittest.main()
