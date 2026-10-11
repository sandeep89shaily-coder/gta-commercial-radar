import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import phase1_test as t

class PhaseOneIntegrationHarnessTests(unittest.TestCase):
 def test_three_cities_only_and_no_ai_automatic_trigger(self):
  self.assertEqual(len(t.MUNICIPAL_SOURCES),6)
  self.assertTrue(all(x.startswith(('brampton_','mississauga_','toronto_')) for x in t.MUNICIPAL_SOURCES))
  commands=' '.join(' '.join(args) for name,args,limit in t.STEPS)
  for must in ('toronto_public_records.py','mississauga_planning_records.py',
               'mississauga_procurement.py','brampton_network.py'):
   self.assertIn(must,commands)
  for excluded in ('simple_start.py','deepseek_daily.py','lead_research.py',
                   'business_discovery.py','peel_pilot.py'):
   self.assertNotIn(excluded,commands)
 def test_aggregate_zip_omits_databases_records_and_raw_logs(self):
  with tempfile.TemporaryDirectory() as folder:
   data=Path(folder)
   (data/'radar.sqlite').write_bytes(b'DONOTSHARE_DATABASE_BYTES')
   (data/'phase1_test_logs').mkdir()
   (data/'phase1_test_logs'/'collector.log').write_text('SECRET RAW LOG')
   report={'started_at':'2026-10-11','generated_at':'2026-10-11',
           'steps':[{'step':'unit','status':'PASS','elapsed_seconds':1,'error_excerpt':''}],
           'archives':[{'city':'brampton','database':'NOT_PRESENT','sources':[]}],
           'catalogues':[]}
   zip_path=data/'PHASE1_TEST_RESULTS.zip'
   with patch.object(t,'DATA',data),patch.object(t,'ZIP_PATH',zip_path):
    t.package(report)
   with zipfile.ZipFile(zip_path) as z:
    self.assertEqual(set(z.namelist()),{'phase1_test_summary.json','phase1_test_summary.txt'})
    payload='\n'.join(z.read(name).decode() for name in z.namelist())
    self.assertNotIn('DONOTSHARE',payload)
    self.assertNotIn('SECRET RAW LOG',payload)
 def test_error_redaction(self):
  source=r'C:\Users\privateName\Documents\Radar error token=superSecret email jane@example.com'
  result=t.redact(source)
  self.assertNotIn('privateName',result)
  self.assertNotIn('superSecret',result)
  self.assertNotIn('jane@example.com',result)
 def test_stage_preflight_does_not_create_empty_main_database(self):
  with tempfile.TemporaryDirectory() as folder:
   data=Path(folder)
   with patch.object(t,'DATA',data), patch.object(t,'ZIP_PATH',data/'PHASE1_TEST_RESULTS.zip'):
    outcome=t.run()
   self.assertEqual(outcome,1)
   self.assertFalse((data/'radar.sqlite').exists())
   self.assertTrue((data/'PHASE1_TEST_RESULTS.zip').exists())
 def test_optional_archives_missing_is_reported_unambiguously(self):
  with tempfile.TemporaryDirectory() as folder:
   with patch.object(t,'DATA',Path(folder)):
    result=t.city_source_summary('mississauga_planning','missing.sqlite')
   self.assertEqual(result['database'],'NOT_PRESENT')
if __name__=='__main__':unittest.main()
