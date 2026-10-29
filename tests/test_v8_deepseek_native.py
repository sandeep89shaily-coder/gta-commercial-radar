import csv, datetime as dt, sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import v8_deepseek_native as mod

ROW={'project_id':'p1430','address':'1430 Birchmount Road, Toronto, ON','city':'Toronto',
 'source_id':'toronto_permit','source_keys':'24 101010','company_name':'',
 'description':'New industrial units development', 'lane':'PERMIT_REVIEW',
 'review_priority':'75','current_source_status':'Under review'}

def response(p):
 if p=='/v1/tools/search':
  return {'results':[{'url':'https://developer.example/project',
       'content':'Project at 1430 Birchmount Road Toronto by Primepoint Ltd; tenant spaces for lease.'}]}
 if p=='/v1/tools/fetch':return {'title':'Developer','content':'Industrial development project at 1430 Birchmount Road Toronto'}
 if p=='/chat/completions':
  return {'choices':[{'finish_reason':'stop','message':{'content':
          '{"operator":"", "developer":"Primepoint Ltd", "contact":"fake@example.com",'
          '"project_stage":"Unknown", "buyer_fit":"Industrial fit-outs",'
          '"next_verification":"Check current occupancy", "caveats":"Unverified",'
          '"source_urls":["https://developer.example/project"]}'}}],
          'usage':{'prompt_tokens':650,'completion_tokens':230}}
 raise AssertionError(p)

class NativeDeepseekTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
  self.db=mod.v5._ledger(self.folder/'v5_ai_budget.sqlite')
  self.day='2026-10-18';self.calls=[]
 def tearDown(self):self.db.close();self.temp.cleanup()
 def api(self,path,payload):self.calls.append((path,payload));return response(path)
 def test_official_api_payloads_and_verified_model(self):
  evidence,stat=mod.fetch_native(ROW,'key',self.db,self.day,0,self.api)
  self.assertEqual(stat['search'],2)
  self.assertEqual(len(evidence),1)
  queries=[x for x in self.calls if x[0]=='/v1/tools/search']
  self.assertEqual(queries[0][1]['need_content'],True)
  result,actual=mod.analyze(ROW,evidence,'key',self.api)
  self.assertEqual(result['developer'],'Primepoint Ltd')
  self.assertEqual(result['contact'],'')
  self.assertEqual(result['source_urls'],'https://developer.example/project')
  self.assertGreater(actual,0)
  self.assertEqual([p for p,v in self.calls if p=='/chat/completions'],['/chat/completions'])
 def test_fetch_when_search_has_no_content(self):
  def api(path,payload):
   if path.endswith('search'):return {'results':[{'url':'https://developer.example/project','content':''}]}
   if path.endswith('fetch'):return response('/v1/tools/fetch')
   return response(path)
  evidence,stats=mod.fetch_native(ROW,'key',self.db,self.day,0,api)
  self.assertEqual(stats['fetch'],1)
  self.assertEqual(evidence[0]['kind'],'FETCHED_MARKDOWN')
 def test_source_only_still_uses_flash(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);csvfile=folder/'projects.csv'
   with csvfile.open('w',newline='',encoding='utf-8') as f:
    wr=csv.DictWriter(f,fieldnames=ROW.keys());wr.writeheader();wr.writerow(ROW)
   def api(path,payload):
    if path.endswith('search'):return {'results':[]}
    if path.endswith('completions'):
     self.assertEqual(payload['model'],'deepseek-flash')
     self.assertEqual(payload['thinking'],{'type':'disabled'})
     return response('/chat/completions')
    self.fail(path)
   result=mod.run(csvfile,folder,key='key',transport=api,max_projects=1,today=dt.date(2026,10,19))
   self.assertEqual(result['ai_calls_attempted'],1)
   self.assertEqual(result['source_only_ai_calls'],1)
   rows=mod.read_csv(folder/'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv')
   self.assertEqual(rows[0]['status'],'AI_SOURCE_RECORD_REVIEW')
   self.assertEqual(rows[0]['contact'],'')
 def test_budget_enforced_before_search(self):
  self.db.execute('INSERT INTO spends VALUES(?,?,?,?,?)',(self.day,'old',0.9995,None,'DONE'));self.db.commit()
  self.assertFalse(mod.ledger_claim(self.db,self.day,'S8:another:0',mod.SEARCH_COST))
 def test_new_daily_ceiling_blocks_prior_excess(self):
  self.assertEqual(mod.DAILY_LIMIT,0.49)
  self.db.execute('INSERT INTO spends VALUES(?,?,?,?,?)',(self.day,'old',0.4995,None,'DONE'));self.db.commit()
  self.assertFalse(mod.ledger_claim(self.db,self.day,'S8:another:0',mod.SEARCH_COST))
  total=self.db.execute('SELECT SUM(reserved) FROM spends WHERE day=?',(self.day,)).fetchone()[0]
  self.assertLessEqual(total,0.50)
 def test_no_key_no_api(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp);csvfile=path/'p.csv'
   with csvfile.open('w',newline='',encoding='utf-8') as f:
    wr=csv.DictWriter(f,fieldnames=ROW.keys());wr.writeheader();wr.writerow(ROW)
   result=mod.run(csvfile,path,key='',transport=lambda *_: self.fail('network call'),today=dt.date(2026,10,19))
   self.assertFalse(result['deepseek_configured']);self.assertEqual(result['ai_calls_attempted'],0)
 def test_source_only_does_not_promote_fabricated_company(self):
  result,_=mod.analyze(ROW,[],'key',self.api)
  self.assertEqual(result['developer'],'')
  self.assertEqual(result['contact'],'')
  self.assertEqual(result['evidence_level'],'SOURCE_RECORD_ONLY')
 def test_empty_search_is_not_billed(self):
  def empty(p,data):return {'results':[]}
  _,s=mod.fetch_native(ROW,'key',self.db,self.day,0,empty)
  self.assertEqual(s['search'],len(mod.queries(ROW)))
  self.assertEqual(self.db.execute('SELECT SUM(reserved) FROM spends').fetchone()[0],0)

if __name__=='__main__':unittest.main()