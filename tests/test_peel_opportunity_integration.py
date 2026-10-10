import sqlite3
from datetime import datetime
from opportunity_engine import collect,export
from peel_pilot import init

def test_peel_baseline_is_not_new_event(tmp_path):
    with sqlite3.connect(tmp_path/'peel_pilot.sqlite') as db:
        init(db)
        db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)',('caledon_development_register','SPA-101','Caledon plaza','https://www.caledon.ca/','','NO_SOURCE_DATE','2026-10-10','2026-10-10','abc'))
    rows,stats,sources=collect(tmp_path,today=datetime(2026,10,10).date())
    assert rows == []
    export(tmp_path,today=datetime(2026,10,10).date())
    audit=(tmp_path/'collector_opportunity_audit.csv').read_text(encoding='utf-8-sig')
    assert 'caledon_development_register,1,0' in audit

def test_peel_post_baseline_change_enters_queue_with_caveat(tmp_path):
    with sqlite3.connect(tmp_path/'peel_pilot.sqlite') as db:
        init(db)
        db.execute('INSERT INTO events (source_id,record_key,change_type,observed_at,title,source_url) VALUES (?,?,?,?,?,?)',('peel_flow_projects','25-1340','UPDATED','2026-10-10T13:00:00+00:00','Baker Road watermain replacement','https://peelregion.ca/construction/project-25-1340'))
    rows,_,_=collect(tmp_path,today=datetime(2026,10,10).date())
    assert len(rows)==1
    assert rows[0]['selection_reason']=='PEEL_POST_BASELINE_CHANGE_OBSERVED_DATE_NOT_ISSUE_DATE'
    assert rows[0]['opportunity_type']=='PUBLIC_INFRASTRUCTURE'
    assert rows[0]['maturity']=='DETECTED'
