import csv
import datetime as dt
import importlib.util
import json
import re
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

FAKE_V5=types.ModuleType('v5_investigator')
FAKE_V5.FIELDS=['project_id','address','source_id','status','priority','operator','developer','project_stage','evidence_date','buyer_fit','contact','source_urls','caveats','web_pages','searches','ai_used','researched_at']
FAKE_V5.INPUT_USD_PER_M=5.0
FAKE_V5.OUTPUT_USD_PER_M=10.0
FAKE_V5.DAILY_BUDGET=.50
FAKE_V5.MODEL='deepseek-chat'
FAKE_V5.API='https://api.deepseek.com/chat/completions'
FAKE_V5.CLOSED=re.compile('closed|withdrawn|refused',re.I)
FAKE_V5.key_from_windows=lambda:''
FAKE_V5.search_rss=lambda query:[]
FAKE_V5.get_html=lambda url:''
def ledger(p):
    db=sqlite3.connect(p)
    db.execute('CREATE TABLE IF NOT EXISTS spends (day TEXT,candidate TEXT,reserved REAL,actual REAL,status TEXT, PRIMARY KEY(day,candidate))')
    db.commit()
    return db
FAKE_V5._ledger=ledger
FAKE_V5._finish=lambda db,day,candidate,status,actual:(db.execute('UPDATE spends SET status=?,actual=? WHERE day=? AND candidate=?',(status,actual,day,candidate)),db.commit())
FAKE_V5._legacy_reserved=lambda path,day:0.0
FAKE_V6=types.ModuleType('v6_daily_pipeline')
FAKE_V6.discover_improved=lambda *a,**kw:([],2)
with patch.dict(sys.modules,{'v5_investigator':FAKE_V5,'v6_daily_pipeline':FAKE_V6}):
    spec=importlib.util.spec_from_file_location('_test_v7_module',(Path(__file__).resolve().parent.parent / 'v7_deepseek_research.py'))
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)

class V7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake_modules=patch.dict(sys.modules,{'v5_investigator':FAKE_V5,'v6_daily_pipeline':FAKE_V6})
        cls.fake_modules.start()
    @classmethod
    def tearDownClass(cls):
        cls.fake_modules.stop()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
        self.date=dt.date(2026,10,19)
        self.projects=self.p/'CANDIDATES_V4_ALL_REVIEW_ONLY.csv'
        self.records=[dict(project_id='A1',lane='PERMIT_REVIEW',address='622 Fogal Rd, Brampton',source_id='brampton_building_permits',
                           company_name='ABC Foods Ltd',description='Interior retail fit-out for ABC Foods Ltd',current_source_status='Applied',review_priority='60'),
                      dict(project_id='A2',lane='PLANNING_WATCH',address='1430 Birchmount Road',source_id='toronto_planning',company_name='',
                           description='Industrial units development',current_source_status='Under Review',review_priority='35')]
        with self.projects.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(self.records[0].keys()));w.writeheader();w.writerows(self.records)
    def tearDown(self):self.tmp.cleanup()
    def response(self,payload):
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'operator':'ABC Foods Ltd','developer':'Made Up Developer',
               'contact':'fake@example.com','project_stage':'Application','evidence_date':'','buyer_fit':'Potential retail fit-out needs',
               'next_verification':'Check Brampton permit status and identify applicant',
               'caveats':'Not an issued permit','source_urls':['https://unsupported.example.com']})}}],
               'usage':{'prompt_tokens':350,'completion_tokens':100}}
    def test_no_corrob_page_does_not_block_ai_and_is_honestly_labeled(self):
        seen=[]
        def post(p):seen.append(p);return self.response(p)
        state=mod.run(self.projects,self.p,key='demo',post=post,max_projects=1,today=self.date)
        self.assertEqual(len(seen),1)
        self.assertEqual(state['ai_calls_attempted'],1)
        self.assertEqual(state['ai_calls_succeeded'],1)
        self.assertEqual(state['with_public_pages'],0)
        row=mod._read(self.p/'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv')[0]
        self.assertEqual(row['status'],'AI_SOURCE_RECORD_REVIEW')
        self.assertEqual(row['operator'],'ABC Foods Ltd')
        self.assertEqual(row['developer'],'')
        self.assertEqual(row['contact'],'')
        self.assertEqual(row['source_urls'],'')
        self.assertIn('SOURCE RECORD ONLY',row['caveats'])
        self.assertIn('Hypothesis only',row['buyer_fit'])
        self.assertIn('next_verification',seen[0]['messages'][0]['content'])
    def test_no_second_day_same_day_double_charge(self):
        once=mod.run(self.projects,self.p,key='demo',post=self.response,max_projects=1,today=self.date)
        twice=mod.run(self.projects,self.p,key='demo',post=self.response,max_projects=1,today=self.date)
        self.assertEqual(once['ai_calls_succeeded'],1)
        self.assertEqual(twice['ai_calls_succeeded'],1) # moves to second previously unprocessed project
        db=ledger(self.p/'v5_ai_budget.sqlite')
        try:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM spends').fetchone()[0],2)
        finally:
            db.close()
        third=mod.run(self.projects,self.p,key='demo',post=lambda *_:self.fail('duplicate call'),max_projects=1,today=self.date)
        self.assertEqual(third['ai_calls_attempted'],0)
    def test_no_key_zero_api_calls(self):
        state=mod.run(self.projects,self.p,key='',post=lambda *_:self.fail('paid API without key'),max_projects=2,today=self.date)
        self.assertEqual(state['ai_calls_attempted'],0)
        self.assertEqual(state['no_key_count'],2)
    def test_shared_budget_blocks_call_even_without_web(self):
        db=ledger(self.p/'v5_ai_budget.sqlite')
        try:
            db.execute('INSERT INTO spends VALUES (?,?,?,?,?)',(self.date.isoformat(),'OLD_V6_PLAN',.49,.05,'DONE'))
            db.commit()
        finally:
            db.close()
        state=mod.run(self.projects,self.p,key='demo',post=lambda *_:self.fail('over budget'),max_projects=2,today=self.date)
        self.assertEqual(state['ai_calls_attempted'],0)
        self.assertEqual(state['ai_budget_deferred'],2)
    def test_external_page_can_count_as_evidence_with_validated_contact(self):
        def discover(*a,**kw):return ([{'url':'https://example.com/abc','text':'ABC Foods Ltd retail permit contact mail@example.com'}],1)
        def post(p):
            r=self.response(p);v=json.loads(r['choices'][0]['message']['content']);v['source_urls']=['https://example.com/abc'];v['contact']='mail@example.com'
            r['choices'][0]['message']['content']=json.dumps(v)
            return r
        state=mod.run(self.projects,self.p,key='demo',post=post,discover=discover,max_projects=1,today=self.date)
        self.assertEqual(state['with_public_pages'],1)
        row=mod._read(self.p/'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv')[0]
        self.assertEqual(row['status'],'AI_EVIDENCE_REVIEW')
        self.assertEqual(row['contact'],'mail@example.com')
        self.assertEqual(row['source_urls'],'https://example.com/abc')
    def test_no_deepseek_for_empty_record(self):
        self.records[0]['description']='';self.records[0]['company_name']=''
        with self.projects.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=self.records[0].keys());w.writeheader();w.writerows(self.records)
        state=mod.run(self.projects,self.p,key='demo',post=self.response,max_projects=1,today=self.date)
        self.assertEqual(state['ai_calls_attempted'],0)
        self.assertEqual(mod._read(self.p/'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv')[0]['status'],'INSUFFICIENT_SOURCE_RECORD')

if __name__=='__main__':unittest.main()