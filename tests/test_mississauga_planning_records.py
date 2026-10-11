import sqlite3
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
from mississauga_planning_records import (load_sources,validate_location,fetch,due,IDS,setup,persist)

class MississaugaPlanningTests(unittest.TestCase):
 def test_two_distinct_disabled_stage_sources(self):
  feeds=load_sources()
  self.assertEqual([s['id'] for s in feeds],list(IDS))
  self.assertTrue(all(not s['enabled'] for s in feeds))
 def test_allow_only_official_city_arcgis_account(self):
  source=load_sources()[0]
  validate_location(source)
  with self.assertRaises(ValueError):
   validate_location({**source,'url':'https://evil.example/x'})
 def test_complete_snapshot_and_stable_application_identifier(self):
  source=load_sources()[0]
  class Http:
   def get(self,url,params=None,**kwargs):
    resp=Mock()
    if url.endswith('/0'):
     resp.json.return_value={'fields':[{'name':'APP_FILE_NO'},{'name':'OBJECTID'}],'objectIdField':'OBJECTID'}
    else:
     resp.json.return_value={'count':2}
    return resp
  snapshot=Mock(rows=[{'APP_FILE_NO':'SP100','OBJECTID':1,'STATUS':'Review'},
                           {'APP_FILE_NO':'SP101','OBJECTID':2,'STATUS':'Approved'}],is_complete=True)
  with patch('mississauga_planning_records.collect_arcgis',return_value=snapshot):
   rows,meta,spec=fetch(Http(),source)
  self.assertEqual(len(rows),2)
  self.assertEqual(meta['reported_count'],2)
  self.assertEqual(spec['keys'],('APP_FILE_NO',))
 def test_duplication_rejected_prior_to_commit(self):
  source=load_sources()[0]
  snapshot=Mock(rows=[{'APP_FILE_NO':'SP100'},{'APP_FILE_NO':'SP100'}],is_complete=True)
  class Http:
   def get(self,url,**kwargs):
    return Mock(json=lambda:{'fields':[{'name':'APP_FILE_NO'},{'name':'OBJECTID'}],
                              'objectIdField':'OBJECTID'} if url.endswith('/0') else {'count':2})
  with patch('mississauga_planning_records.collect_arcgis',return_value=snapshot):
   with self.assertRaisesRegex(ValueError,'Duplicate rows|missing or repeated'):
    fetch(Http(),source)
 def test_history_and_weekly_gating(self):
  con=sqlite3.connect(':memory:')
  setup(con)
  spec={'id':IDS[0],'department':'City Planning','keys':('APP_FILE_NO',)}
  meta={'package_id':'official-service','resource_id':'layer0',
        'resource_url':'https://example.org/layer','source_url':'https://example.org/layer'}
  t=datetime(2026,10,11,tzinfo=timezone.utc)
  persist(con,spec,[{'APP_FILE_NO':'SP100','STATUS':'Review'}],meta,t.isoformat())
  self.assertFalse(due(con,IDS[0],t+timedelta(days=6)))
  self.assertTrue(due(con,IDS[0],t+timedelta(days=8)))
  self.assertEqual(con.execute('SELECT COUNT(*) FROM changes').fetchone()[0],0)
  persist(con,spec,[{'APP_FILE_NO':'SP100','STATUS':'Approved'}],meta,(t+timedelta(days=8)).isoformat())
  self.assertEqual(con.execute('SELECT COUNT(*) FROM changes').fetchone()[0],1)
  con.close()
if __name__=='__main__':unittest.main()
