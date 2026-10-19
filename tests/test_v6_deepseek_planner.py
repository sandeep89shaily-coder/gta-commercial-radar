import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import v5_investigator as v5
import v6_deepseek_planner as plan


class DeepSeekFirstResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=v5._ledger(Path(self.tmp.name)/'budget.sqlite')
        self.row={'project_id':'commercial-01','address':'1430 Birchmount Road, Toronto',
                  'description':'proposed commercial industrial building'}
        self.day='2026-10-18'

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def model(self,payload):
        self.assertEqual(payload['model'],v5.MODEL)
        self.assertIn('queries',payload['messages'][0]['content'])
        return {'choices':[{'finish_reason':'stop','message':{'content':
          '{"queries":["1430 Birchmount Road Toronto developer 2026",'
          '"1430 Birchmount industrial planning application"]}'}}],
          'usage':{'prompt_tokens':200,'completion_tokens':75}}

    def test_deepseek_is_called_before_any_webpage_exists(self):
        with patch.object(plan,'urlopen',side_effect=AssertionError('network')):
            result=plan.research(self.row,'demo-secret',self.db,self.day,post=self.model)
        self.assertEqual(result['status'],'PLANNED')
        self.assertTrue(result['attempted'])
        self.assertEqual(len(result['queries']),2)
        entry=self.db.execute('SELECT reserved,actual,status FROM spends').fetchone()
        self.assertEqual(entry[2],'DONE')
        self.assertLess(entry[1],entry[0])
        self.assertLessEqual(entry[0],0.50)

    def test_duplicate_same_day_rejected_before_model_call(self):
        plan.research(self.row,'demo-secret',self.db,self.day,post=self.model)
        result=plan.research(self.row,'demo-secret',self.db,self.day,
                             post=lambda *_:self.fail('DeepSeek should not run twice'))
        self.assertEqual(result['status'],'BUDGET_OR_DUPLICATE')
        self.assertFalse(result['attempted'])

    def test_no_key_never_calls_provider(self):
        result=plan.research(self.row,'',self.db,self.day,
                             post=lambda *_:self.fail('No key'))
        self.assertEqual(result['status'],'NO_KEY')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM spends').fetchone()[0],0)

    def test_exhausted_budget_suppresses_paid_calls(self):
        self.db.execute("INSERT INTO spends VALUES (?,?,?,?,?)",
                        (self.day,'prior',0.495,0.495,'DONE'))
        self.db.commit()
        result=plan.research(self.row,'demo-secret',self.db,self.day,
                             post=lambda *_:self.fail('Exceeded budget'))
        self.assertEqual(result['status'],'BUDGET_OR_DUPLICATE')

    def test_model_error_keeps_budget_reservation(self):
        result=plan.research(self.row,'demo-secret',self.db,self.day,
                             post=lambda *_:{'choices':[{'finish_reason':'length'}]})
        self.assertEqual(result['status'],'ERROR')
        self.assertEqual(self.db.execute('SELECT status FROM spends').fetchone()[0],'ERROR')


if __name__=='__main__':
    unittest.main()
