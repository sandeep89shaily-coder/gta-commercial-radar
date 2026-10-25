import csv
from contextlib import closing
import datetime as dt
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_FILE=Path(__file__).resolve().parents[1]/'v6_daily_pipeline.py'
spec=importlib.util.spec_from_file_location('v6_daily_pipeline',MODULE_FILE)
v6=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v6;spec.loader.exec_module(v6)


class V6Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.ws=Path(self.tmp.name)/'new data';self.ws.mkdir()
        self.data=self.ws/'GTA_RADAR_DAILY_48H'/'data';self.data.mkdir(parents=True)
        self.db=self.data/'radar.sqlite'
        with closing(sqlite3.connect(self.db)) as db:
            db.execute('CREATE TABLE records_current (source_id TEXT, record_key TEXT, source_date TEXT, normalized_json TEXT, active INTEGER)')
            db.execute("INSERT INTO records_current VALUES('toronto_active_building_permits','A1','2026-10-18','{}',1)")
            db.commit()
        self.results=self.ws/'GTA_RADAR_RESULTS'

    def tearDown(self):self.tmp.cleanup()

    def test_finds_existing_database_without_creating_another(self):
        self.assertEqual(v6.choose_database(self.ws).resolve(),self.db.resolve())
        self.assertEqual(len(list(self.ws.rglob('radar.sqlite'))),1)

    def test_makes_no_stale_export_when_collectors_fail(self):
        def fails(name,args,logs,**kwargs):
            return {'step':name,'status':'FAILED','detail':'offline'}
        with patch.object(v6,'render_dashboard',return_value=None):
            outcome=v6.pipeline(self.ws,self.db,collector=fails,investigator=lambda *_a,**_kw: self.fail('AI ran'))
        self.assertEqual(outcome['status'],'FAILED')
        self.assertEqual(outcome['projects'],0)
        self.assertFalse((self.data/'opportunities_ALL_REVIEW_ONLY.csv').exists())
        self.assertFalse((self.results/'V6_RUNNING.lock').exists())
        self.assertEqual(json.loads((self.results/'GTA_RADAR_V6_RUN.json').read_text())['status'],'FAILED')

    def test_complete_daily_chain_runs_collectors_before_selector_and_ai(self):
        events=[]
        def collector(name,args,logs,**kwargs):
            events.append(name)
            if name=='fresh_48h_opportunities':
                with (self.data/'opportunities_ALL_REVIEW_ONLY.csv').open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=['source_id','source_key','description','address']);w.writeheader()
                    w.writerow({'source_id':'toronto_active_building_permits','source_key':'1','description':'industrial warehouse','address':'100 Office Rd'})
            return {'step':name,'status':'SUCCESS','detail':'complete'}
        def selector(src,dst,db):
            events.append('selector');self.assertTrue(Path(src).exists())
            with (Path(dst)/'CANDIDATES_V4_ALL_REVIEW_ONLY.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['project_id','address']);w.writeheader();w.writerow({'project_id':'A','address':'100 Office Rd'})
        def investigator(data,results,max_projects):
            events.append('investigator');self.assertEqual(max_projects,0)
            return {'processed':1,'with_public_pages':1,'reserved_usd':0.02,'deepseek_configured':True}
        outcome=v6.pipeline(self.ws,self.db,collector=collector,selector=selector,investigator=investigator)
        self.assertEqual(outcome['status'],'SUCCESS')
        self.assertEqual(outcome['investigated'],1)
        self.assertEqual(events,['municipal_collector','business_collector',
            'early_planning_pilot','early_industrial_cues','early_agendas',
            'early_hamilton','early_notices','early_ajax','early_oakville',
            'early_markham','early_investment_tenders','fresh_48h_opportunities',
            'selector','investigator'])
        self.assertTrue((self.results/'GTA_RADAR_V6_DASHBOARD.html').exists())
        self.assertFalse((self.results/'V6_RUNNING.lock').exists())

    def test_ai_exception_writes_diagnostic_and_retains_checkpoint(self):
        (self.data/'opportunities_ALL_REVIEW_ONLY.csv').write_text(
            'source_id,source_key,description,address\n'
            'toronto_active_building_permits,permit-1,Office renovation,\n',
            encoding='utf-8')
        def selector(source, out, db):
            (Path(out)/'CANDIDATES_V4_ALL_REVIEW_ONLY.csv').write_text(
                'project_id,source_id,address,description\n'
                'project-1,toronto_active_building_permits,,Office renovation\n',
                encoding='utf-8')
        def investigator(*_args,**_kwargs):
            latest=self.results/'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv'
            latest.write_text(
                'project_id,investigated_local_date,status\n'
                'project-1,2026-10-20,AI_EVIDENCE_REVIEW\n',encoding='utf-8')
            raise IndexError('list index out of range')
        outcome=v6.pipeline(self.ws,self.db,run_collectors=False,selector=selector,
                            investigator=investigator,results_dir=self.results,
                            today=dt.date(2026,10,20))
        self.assertEqual(outcome['status'],'FAILED')
        self.assertEqual(outcome['error_stage'],'DEEPSEEK_RESEARCH')
        self.assertIn('IndexError:',outcome['error'])
        self.assertEqual(outcome['checkpointed_investigations_today'],1)
        diagnostic=Path(outcome['error_log'])
        self.assertTrue(diagnostic.is_file())
        self.assertIn('in investigator',diagnostic.read_text())
        self.assertIn('IndexError:',diagnostic.read_text())
        dashboard=(self.results/'GTA_RADAR_V6_DASHBOARD.html').read_text()
        self.assertIn('DEEPSEEK_RESEARCH',dashboard)
        self.assertIn('Research records checkpointed',dashboard)
        manifest=json.loads((self.results/'GTA_RADAR_V6_RUN.json').read_text())
        self.assertEqual(manifest['error_stage'],'DEEPSEEK_RESEARCH')
        self.assertFalse((self.results/'V6_RUNNING.lock').exists())

    def test_partial_collectors_not_silently_reported_fresh(self):
        def collector(name,args,logs,**kwargs):
            if name=='fresh_48h_opportunities':
                (self.data/'opportunities_ALL_REVIEW_ONLY.csv').write_text('source_id,source_key,description,address\n',encoding='utf-8')
            return {'step':name,'status':'FAILED' if name=='municipal_collector' else 'SUCCESS','detail':'test'}
        def select(*_):
            with (self.results/'CANDIDATES_V4_ALL_REVIEW_ONLY.csv').open('w') as f:f.write('project_id,address\n')
        outcome=v6.pipeline(self.ws,self.db,collector=collector,selector=select,
                            investigator=lambda *_a,**_kw:{'processed':0,'with_public_pages':0,'reserved_usd':0,'deepseek_configured':False})
        self.assertEqual(outcome['status'],'PARTIAL')
        html=(self.results/'GTA_RADAR_V6_DASHBOARD.html').read_text()
        self.assertIn('Collection attention needed',html)

    def test_optional_early_pilot_failure_does_not_block_core_research(self):
        events=[]
        def collector(name,args,logs,**kwargs):
            events.append(name)
            if name=='fresh_48h_opportunities':
                (self.data/'opportunities_ALL_REVIEW_ONLY.csv').write_text(
                    'source_id,source_key,description,address\n',encoding='utf-8')
            if name=='early_oakville':
                return {'step':name,'status':'FAILED','detail':'offline pilot'}
            return {'step':name,'status':'SUCCESS','detail':'done'}
        def selector(src,dst,db):
            (Path(dst)/'CANDIDATES_V4_ALL_REVIEW_ONLY.csv').write_text(
                'project_id,address\n',encoding='utf-8')
        outcome=v6.pipeline(self.ws,self.db,collector=collector,selector=selector,
            investigator=lambda *_a,**_kw:{'processed':0,'with_public_pages':0,
                                           'reserved_usd':0,'deepseek_configured':False})
        self.assertEqual(outcome['status'],'SUCCESS')
        self.assertIn('early_oakville',events)
        self.assertIn({'step':'early_oakville','status':'FAILED'},outcome['early_pilot_results'])

    def test_week_cooldown_skips_recently_investigated(self):
        import types
        stub=types.SimpleNamespace(CLOSED=v6.re.compile(r'closed',v6.re.I))
        with patch.dict(sys.modules,{'v5_investigator':stub}), patch.object(v6,'v5_original_queue',lambda rs,limit,prev,day:rs[:limit]):
            rows=[{'project_id':'recent','current_source_status':'Open'},{'project_id':'fresh','current_source_status':'Open'},
                  {'project_id':'closed','current_source_status':'closed'}]
            prior={'recent':{'researched_at':'2026-10-18T07:00:00'}}
            result=v6.select_unresearched(rows,25,prior,dt.date(2026,10,18))
            self.assertEqual([x['project_id'] for x in result],['fresh'])

    def test_evidence_discovery_is_source_matched(self):
        import types
        stub=types.SimpleNamespace(location_match=lambda row,page:'1440 Birchmount' in page)
        with patch.dict(sys.modules,{'v5_investigator':stub}):
            sample={'address':'1440 Birchmount Road, Toronto','description':'industrial site'}
            def search(q):return ['https://example.org/unrelated','https://example.org/project']
            def fetch(u):return 'unrelated' if u.endswith('/unrelated') else '1440 Birchmount commercial works'
            ev,requests=v6.discover_improved(sample,search,fetch)
            self.assertEqual(len(ev),1)
            self.assertEqual(ev[0]['url'],'https://example.org/project')
            self.assertGreaterEqual(requests,2)

    def test_dashboard_escapes_untrusted_data(self):
        self.results.mkdir()
        with (self.results/'GTA_RADAR_V5_INVESTIGATIONS.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['address','project_id','status','researched_at','source_urls','caveats']);w.writeheader()
            w.writerow({'address':'<script>alert(1)</script>','project_id':'danger','status':'NO_EVIDENCE','researched_at':'2026-10-18','source_urls':'javascript:alert(1)','caveats':'<b>unsafe</b>'})
        file=v6.render_dashboard(self.results,{'status':'SUCCESS','investigation_date':'2026-10-18','steps':[]})
        contents=file.read_text()
        self.assertNotIn('<script>alert(1)</script>',contents)
        self.assertNotIn('href="javascript:',contents)
        self.assertIn('&lt;b&gt;unsafe&lt;/b&gt;',contents)

    def test_same_folder_lock_prevents_overlapping_runs(self):
        self.results.mkdir()
        first=v6.once_lock(self.results)
        with self.assertRaises(RuntimeError):v6.once_lock(self.results)
        first.unlink()


if __name__=='__main__':unittest.main()