import unittest, tempfile, csv, json, datetime as dt, hashlib, sqlite3, subprocess, sys
from contextlib import closing
from pathlib import Path
import v5_investigator as v

class V5EvidenceTests(unittest.TestCase):
    def row(self):
        return dict(project_id='test-fogal',lane='PERMIT_REVIEW',
                    address='622 Fogal Rd, Brampton',source_id='brampton_building_permits',
                    source_keys='26-169635-000-00',review_priority='65',
                    current_source_status='Applied',company_name='UNKNOWN',
                    description='Retail interior fit out')
    def seed(self,folder):
        row=self.row()
        v.write_rows(folder/'CANDIDATES_V4_ALL_REVIEW_ONLY.csv',[row],list(row))
    def test_evidence_first_ai_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as name:
            d=Path(name);self.seed(d);calls=[]
            def mocked_ai(payload):
                calls.append(payload)
                return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({
                  'operator':'Fabricated Ltd','developer':'Real Builders Inc','contact':'fake@example.com',
                  'project_stage':'Applied','evidence_date':'2026','buyer_fit':'HVAC to research',
                  'source_urls':['https://example.org/permit'],'caveats':'Not verified'})}}],
                  'usage':{'prompt_tokens':100,'completion_tokens':120}}
            args=dict(key='placeholder',search=lambda q:['https://example.org/permit'],
                      fetch=lambda u:'622 Fogal Rd Brampton permit; applicant Real Builders Inc',
                      post=mocked_ai,today=dt.date(2026,10,17))
            first=v.run(d,**args)
            self.assertEqual(len(calls),1)
            self.assertLessEqual(first['reserved_usd'],1.00)
            candidate=v.read_rows(d/'GTA_RADAR_V5_INVESTIGATIONS.csv')[0]
            self.assertEqual(candidate['developer'],'Real Builders Inc')
            self.assertEqual(candidate['operator'],'')
            self.assertEqual(candidate['contact'],'')
            next_run=v.run(d,**args)
            self.assertEqual(len(calls),1)
            self.assertEqual(next_run['cached_today'],1)
    def test_no_source_no_charges(self):
        with tempfile.TemporaryDirectory() as name:
            d=Path(name);self.seed(d)
            result=v.run(d,key='placeholder',search=lambda q:[],fetch=lambda u:'',post=lambda x:self.fail('AI called'))
            self.assertEqual(result['reserved_usd'],0)
            self.assertEqual(v.read_rows(d/'GTA_RADAR_V5_INVESTIGATIONS.csv')[0]['status'],'NO_CORROBORATED_PAGE')
    def test_legacy_spend_cap(self):
        with tempfile.TemporaryDirectory() as name:
            d=Path(name);self.seed(d)
            with closing(sqlite3.connect(d/'deepseek_budget.sqlite')) as db:
                db.execute('CREATE TABLE spends (date TEXT,reserved REAL)')
                db.execute('INSERT INTO spends VALUES (?,?)',('2026-10-17',0.99))
                db.commit()
            result=v.run(d,key='placeholder',today=dt.date(2026,10,17),
                search=lambda q:['https://example.org/permit'],fetch=lambda u:'622 Fogal Rd',
                post=lambda x:self.fail('AI called'))
            self.assertLessEqual(result['reserved_usd'],1.00)
            self.assertEqual(v.read_rows(d/'GTA_RADAR_V5_INVESTIGATIONS.csv')[0]['status'],'DAILY_BUDGET_OR_ALREADY_USED')
    def test_refused_application_not_selected(self):
        r=self.row();closed=dict(r,project_id='closed',current_source_status='Refused')
        self.assertEqual(len(v.select_queue([r,closed])),1)

class V5OneClickTests(unittest.TestCase):
    def test_missing_export_and_readonly_db(self):
        launcher=Path(__file__).resolve().parents[1]/'GTA_RADAR_V5_ONE_CLICK.bat'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'new data'
            data=root/'GTA_RADAR_DAILY_48H'/'data'
            data.mkdir(parents=True)
            dbfile=data/'radar.sqlite'
            date=dt.date.today().isoformat()
            with closing(sqlite3.connect(dbfile)) as db:
                db.execute('CREATE TABLE records_current(source_id TEXT,record_key TEXT,source_date TEXT,normalized_json TEXT,active INTEGER,PRIMARY KEY(source_id,record_key))')
                db.execute('CREATE TABLE changes(source_id TEXT,record_key TEXT,observed_at TEXT,change_type TEXT,normalized_json TEXT)')
                info={'description':'Retail interior finish commercial restaurant','entity_name':'Fictional Foods',
                      'address':'622 Fogal Rd','region':'Brampton','status':'Applied'}
                db.execute('INSERT INTO records_current VALUES (?,?,?,?,?)',
                           ('brampton_building_permits','26-169635-000-00',date,json.dumps(info),1))
                db.commit()
            checksum=hashlib.sha256(dbfile.read_bytes()).hexdigest()
            result=subprocess.run([sys.executable,'-x',str(launcher),'--root',str(root),
                                   '--offline','--no-open','--no-schedule'],
                                   capture_output=True,text=True,timeout=50)
            self.assertEqual(result.returncode,0,result.stdout+'\\n'+result.stderr)
            self.assertEqual(hashlib.sha256(dbfile.read_bytes()).hexdigest(),checksum)
            self.assertTrue((root/'GTA_RADAR_RESULTS'/'GTA_RADAR_V5_DASHBOARD.html').exists())
            self.assertEqual(json.loads((root/'GTA_RADAR_RESULTS'/'GTA_RADAR_V5_RUN.json').read_text())['reserved_usd'],0)

if __name__=='__main__':unittest.main()
