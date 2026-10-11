"""Mississauga post-baseline, evidence-linked commercial RESEARCH signals.

Combines public GIS application version observations and legacy publicly listed
bid changes. Does NOT infer fresh business openings, tender eligibility,
approvals, awarded work, or opportunities from initial baselines.
"""
from __future__ import annotations
import csv,json,sqlite3
from pathlib import Path
from toronto_signals import categories

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
OUT=DATA/'mississauga_service_provider_signals_REVIEW_ONLY.csv'
FIELDS=('observed_at','source_id','record_key','change_type','signal_type',
        'provider_categories','application_or_bid_id','title','address',
        'source_status','published_date','published_amount','source_url',
        'qualification','notes')
SOURCES={
 'mississauga_site_plan_applications':'SITE_PLAN_APPLICATION_CHANGE',
 'mississauga_rezoning_applications':'REZONING_APPLICATION_CHANGE',
 'mississauga_bidsandtenders_legacy':'PUBLIC_BID_LISTING_CHANGE',
}

def pick(row,*names):
 for name in names:
  val=str(row.get(name) or '').strip()
  if val:return val
 return ''

def translate(change,record):
 source=change['source_id']
 if source not in SOURCES:return None
 is_bid=source=='mississauga_bidsandtenders_legacy'
 text=pick(record,'TITLE','PROJECT_NAME','DESCRIPTION','PROJECT_DESCRIPTION',
           'WORK_DESCRIPTION','PUBLIC_LISTING_TEXT','PURPOSE','TYPE')
 status=pick(record,'STATUS','APPLICATION_STATUS','APPLICATION_STATE','LATEST_MILESTONE')
 key=pick(record,'APP_FILE_NO','BID_NUMBER') or change['record_key']
 detail=pick(record,'DETAIL_URL','EVIDENCE_URL')
 base=str(change.get('source_url') or '')
 url=detail if detail.startswith('https://') else base
 return {'observed_at':change['observed_at'],
  'source_id':source,'record_key':change['record_key'],
  'change_type':change['change_type'],'signal_type':SOURCES[source],
  'provider_categories':categories(' '.join((text,status))),
  'application_or_bid_id':key,'title':text[:700],
  'address':pick(record,'ADDRESS','SITE_ADDRESS','FULL_ADDRESS','LOCATION'),
  'source_status':status,
  'published_date':pick(record,'CLOSING_DATE','APPLICATION_DATE','DATE_RECEIVED','ISSUED_DATE'),
  'published_amount':pick(record,'ESTIMATED_VALUE','PROJECT_VALUE','AWARD_AMOUNT'),
  'source_url':url,'qualification':'REQUIRES_INDEPENDENT_REVIEW',
  'notes':('Published bid listing changed; verify if opportunity is open and closing date independently.'
           if is_bid else
           'Planning record changed; verify decision, stage, applicant and commercial use before contacting providers.')}

def archive_changes(path,allowed):
 if not path.is_file():return []
 con=sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True)
 con.row_factory=sqlite3.Row
 try:
  changes=con.execute('SELECT source_id,record_key,observed_at,change_type,source_url,new_hash '
                      'FROM changes ORDER BY id DESC LIMIT 3000').fetchall()
  output=[]
  for row in changes:
   change=dict(row)
   if change['source_id'] not in allowed:continue
   old=con.execute('SELECT json FROM versions WHERE source_id=? AND record_key=? '
                   'AND hash=? AND observed_at<=? ORDER BY id DESC LIMIT 1',
                   (change['source_id'],change['record_key'],change['new_hash'],change['observed_at'])).fetchone()
   if not old:continue
   try:record=json.loads(old['json'])
   except (ValueError,TypeError):continue
   if not isinstance(record,dict):continue
   result=translate(change,record)
   if result:output.append(result)
  return output
 finally:con.close()

def run():
 if not any((DATA/file).is_file() for file in ('mississauga_planning_sources.sqlite',
                                               'mississauga_procurement_sources.sqlite')):
  raise RuntimeError('Mississauga municipal archives not yet available; refusing misleading empty signals')
 results=archive_changes(DATA/'mississauga_planning_sources.sqlite',
                          {'mississauga_site_plan_applications','mississauga_rezoning_applications'})
 results+=archive_changes(DATA/'mississauga_procurement_sources.sqlite',
                          {'mississauga_bidsandtenders_legacy'})
 results.sort(key=lambda r:r['observed_at'],reverse=True)
 temp=OUT.with_suffix('.csv.tmp')
 with temp.open('w',encoding='utf-8-sig',newline='') as file:
  writer=csv.DictWriter(file,fieldnames=FIELDS)
  writer.writeheader()
  writer.writerows(results)
 temp.replace(OUT)
 print('Mississauga research signals:',len(results),'post-baseline source changes requiring review')
if __name__=='__main__':run()
