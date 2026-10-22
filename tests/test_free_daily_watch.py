"""Free 8:30 AM municipal watch, no paid DeepSeek and no false 'new permit' labels."""
from __future__ import annotations
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import free_daily_report as free
import v6_daily_pipeline as v6

DATE=dt.date(2026,10,21)
def make_row(**extra):
    row=dict(project_id='brampton_building_permits:26-111',
             address='100 Industrial Way Brampton',city='Brampton',
             source_id='brampton_building_permits',source_keys='26-111',
             lane='PERMIT_REVIEW',
             source_group='MUNICIPAL_CHANGE',
             description='New warehouse expansion and sprinkler installation',
             event_date='2026-10-21',
             date_basis='SOURCE RECORD UPDATE OBSERVED — NOT ISSUANCE/OPENING',
             source_record_date='2026-10-19',
             current_source_status='Under Review',review_priority='85')
    row.update(extra)
    return row

def save(path,rows):
    cols=list(dict.fromkeys(k for row in rows for k in row)) if rows else ['project_id']
    with open(path,'w',encoding='utf-8-sig',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=cols);w.writeheader();w.writerows(rows)

class FreeDailyWatchTests(unittest.TestCase):
    def test_initial_run_is_baseline_not_fake_permit_issuance(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inp=root/'candidates.csv'
            save(inp,[make_row(),make_row(project_id='waterloo_city_building_permits:old',
                                          source_group='REGIONAL_ARCHIVED_SOURCE',
                                          description='Industrial facility old addition')])
            result=free.build(inp,root,today=DATE)
            self.assertEqual(result['new_or_changed'],0)
            self.assertEqual(result['initial_baseline'],1)
            self.assertEqual(result['archive_context'],1)
            self.assertEqual(result['ai_calls'],0)
            self.assertEqual(result['deepseek_cost_usd'],0)
            self.assertEqual(len(free._read(root/free.CSV_NAME)),0)
            self.assertIn('NOT municipal permit issue date',
                          (root/free.HTML_NAME).read_text(encoding='utf-8'))
            self.assertEqual(free._read(root/free.ALL_NAME)[0]['observation'],'INITIAL_BASELINE')

    def test_second_run_is_only_new_or_materially_changed_events(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inp=root/'candidates.csv'
            first=make_row()
            save(inp,[first]);free.build(inp,root,today=DATE)
            save(inp,[first,make_row(project_id='brampton_building_permits:26-222',
                                     current_source_status='Applied')])
            follow=free.build(inp,root,today=DATE+dt.timedelta(days=1))
            self.assertEqual((follow['first_observed'],follow['record_changed']),(1,0))
            self.assertEqual(len(free._read(root/free.CSV_NAME)),1)
            newer=dict(first,current_source_status='Issued')
            save(inp,[newer,make_row(project_id='brampton_building_permits:26-222',
                                     current_source_status='Applied')])
            third=free.build(inp,root,today=DATE+dt.timedelta(days=2))
            self.assertEqual(third['record_changed'],1)
            csv=free._read(root/free.CSV_NAME)
            self.assertEqual(csv[0]['observation'],'RECORD_CHANGED')
            self.assertEqual(csv[0]['first_seen_local'],DATE.isoformat())

    def test_rolling_event_date_alone_does_not_create_update(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'items.csv'
            save(p,[make_row()]);free.build(p,root,today=DATE)
            save(p,[make_row(event_date='2026-10-22')])
            r=free.build(p,root,today=DATE+dt.timedelta(days=1))
            self.assertEqual(r['record_changed'],0)

    def test_archival_event_not_new_even_when_indexed_later(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'items.csv'
            save(p,[make_row()]);free.build(p,root,today=DATE)
            save(p,[make_row(),make_row(project_id='niagara:2025:88',
               source_group='REGIONAL_ARCHIVED_SOURCE',event_date='2025-11-01')])
            r=free.build(p,root,today=DATE+dt.timedelta(days=1))
            self.assertEqual(r['first_observed'],0)
            self.assertEqual(r['archive_context'],1)

    def test_no_deepseek_pipeline_preserves_existing_ai_history(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);ws=root/'new data';ws.mkdir()
            d=ws/'GTA_RADAR_BRAMPTON_REPAIRED'/'data';d.mkdir(parents=True)
            db=d/'radar.sqlite';db.write_bytes(b'original data')
            results=ws/'GTA_RADAR_RESULTS';results.mkdir()
            old_ai=results/'GTA_RADAR_V8_INVESTIGATIONS.csv'
            old_ai.write_text('project_id,status\nold,AI_EVIDENCE_REVIEW\n',encoding='utf-8')
            def collector(name,args,logs,**kwargs):
                if name=='fresh_48h_opportunities':
                    save(d/'opportunities_ALL_REVIEW_ONLY.csv',
                         [dict(source_id='brampton_building_permits',source_key='26-111',
                               description='New industrial warehouse',address='100 Industrial Way')])
                return dict(step=name,status='SUCCESS',detail='ok')
            def selector(src,out,db_path):
                save(Path(out)/'CANDIDATES_V4_ALL_REVIEW_ONLY.csv',[make_row()])
            def never_ai(*a,**kw):self.fail("DeepSeek called in free mode")
            with patch.object(v6,'render_dashboard',wraps=v6.render_dashboard):
                state=v6.pipeline(ws,db,run_research=False,collector=collector,
                                  selector=selector,investigator=never_ai,today=DATE)
            self.assertEqual(state['status'],'SUCCESS')
            self.assertEqual(state['ai_mode'],'OFF')
            self.assertEqual(state['free_daily_watch']['ai_calls'],0)
            self.assertEqual(old_ai.read_text(encoding='utf-8'),
                             'project_id,status\nold,AI_EVIDENCE_REVIEW\n')
            self.assertTrue((results/free.HTML_NAME).is_file())
            self.assertIn('DeepSeek calls: 0',(results/'GTA_RADAR_V6_DASHBOARD.html').read_text(encoding='utf-8'))

    def test_schedule_explicitly_includes_no_ai_and_enables_disabled_task(self):
        completed=SimpleNamespace(returncode=0,stderr='',stdout='')
        runner=Path('C:/ProgramData/Radar/RUN_GTA_RADAR_V6.bat')
        workspace=Path('C:/Users/sande/Desktop/new data')
        with patch.object(v6.os,'name','nt'),patch.object(v6.subprocess,'run',return_value=completed) as shell:
            result=v6.schedule_daily(runner,workspace,no_ai=True)
        self.assertTrue(result.startswith('SUCCESS'))
        calls=[call.args[0] for call in shell.call_args_list]
        created=next(x for x in calls if '/Create' in x)
        self.assertIn('--unattended --no-ai',created[created.index('/TR')+1])
        self.assertTrue(any('/Change' in x and '/ENABLE' in x for x in calls))

    def test_failed_task_enable_is_reported_not_silent_success(self):
        ok=SimpleNamespace(returncode=0,stderr='',stdout='')
        fail=SimpleNamespace(returncode=1,stderr='Task is disabled',stdout='')
        runner=Path('RUN_GTA_RADAR_V6.bat')
        workspace=Path('.')
        with patch.object(v6.os,'name','nt'),patch.object(v6.subprocess,'run',side_effect=[ok,fail]) as shell:
            result=v6.schedule_daily(runner,workspace,no_ai=True)
        self.assertIn('FAILED_TO_ENABLE_FREE_TASK',result)

if __name__=='__main__':
    unittest.main()
