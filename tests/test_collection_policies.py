import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import ast, pathlib, json
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
module=ast.parse((ROOT/'main.py').read_text())
fn=next(x for x in module.body if isinstance(x,ast.FunctionDef) and x.name=='collection_plan')
namespace={'datetime':datetime,'timezone':timezone,'timedelta':timedelta}
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(ROOT/'main.py'),'exec'),namespace)
collection_plan=namespace['collection_plan']
def load_sources():return json.loads((ROOT/'config'/'sources.json').read_text())

class PolicyTests(unittest.TestCase):
 def test_all_eleven_have_explicit_policies(self):
  selected={s['id']:s for s in load_sources() if 'collection_policy' in s}
  self.assertEqual(11,len(selected))
  self.assertEqual(9,sum(s['collection_policy']=='snapshot' for s in selected.values()))
  self.assertEqual(2,sum(s['collection_policy']=='incremental' for s in selected.values()))
  self.assertTrue(all(not s['enabled'] for s in selected.values()))
 def plan(self,record_count,days_since,policy='snapshot',cadence=7,force=False):
  now=datetime(2026,10,9,tzinfo=timezone.utc)
  namespace['current_active_count']=lambda *a:record_count
  namespace['last_successful_run']=lambda *a:{'finished_at':(now-timedelta(days=days_since)).isoformat()}
  return collection_plan(None,{'id':'x','collection_policy':policy,'snapshot_interval_days':cadence},force_full=force,now=now)
 def test_fresh_snapshot_skips(self):self.assertEqual('skip',self.plan(100,1))
 def test_due_snapshot_full(self):self.assertEqual('full',self.plan(100,8))
 def test_first_baselines(self):self.assertEqual('full',self.plan(0,1))
 def test_reconcile_full(self):self.assertEqual('full',self.plan(100,1,force=True))
 def test_incremental(self):self.assertEqual('incremental',self.plan(100,1,policy='incremental'))
