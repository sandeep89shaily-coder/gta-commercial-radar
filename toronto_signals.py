"""Evidence-grounded Toronto service-provider research signals, NOT verified leads.

Reads only post-baseline changes from toronto_priority_sources.sqlite. Never
treats archival baseline snapshots, missing rows or council meeting dates as
new businesses, awards or impending purchases.
"""
from __future__ import annotations
import csv, json, sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
OUTPUT=DATA/'toronto_service_provider_signals_REVIEW_ONLY.csv'
FIELDS=('observed_at','source_id','record_key','source_change','signal_type',
        'relevant_provider_categories','published_date','published_status',
        'organization','description','address_or_road','published_value',
        'source_url','qualification','notes')
TYPES={
 'toronto_open_solicitations':'SOLICITATION_RECORD_CHANGE',
 'toronto_awarded_contracts':'AWARDED_CONTRACT_RECORD_CHANGE',
 'toronto_noncompetitive_contracts':'NONCOMPETITIVE_AWARD_RECORD_CHANGE',
 'toronto_road_restrictions':'ROAD_RESTRICTION_RECORD_CHANGE',
 'toronto_development_pipeline':'DEVELOPMENT_PIPELINE_RECORD_CHANGE',
 'toronto_development_application_history':'PLANNING_APPLICATION_RECORD_CHANGE',
}
TAGS={
 'HVAC':('hvac','air conditioning','ventilation','heating','chiller','cooling'),
 'ELECTRICAL':('electrical','electrician','transformer','power distribution'),
 'SECURITY':('security system','cctv','access control','surveillance'),
 'CONSTRUCTION':('construction','renovation','demolition','building works','retrofit'),
 'PLUMBING':('plumbing','sewer','watermain','water main'),
 'IT_SERVICES':('software','cloud service','information technology','network infrastructure'),
 'ENGINEERING':('engineering consulting','engineering services','design-build','design build'),
}

def first(row,*keys):
 for k in keys:
  value=str(row.get(k) or '').strip()
  if value:return value
 return ''

def categories(text):
 value=' '.join(str(text or '').lower().split())
 tags=[name for name,terms in TAGS.items() if any(term in value for term in terms)]
 return ';'.join(tags) if tags else 'UNCLASSIFIED'

def signal(change,row):
 sid=change['source_id']
 if sid not in TYPES:return None
 description=first(row,'DESCRIPTION','SHORT_DESCRIPTION','WORK_DESC','PROJECT_DESCRIPTION',
                   'TITLE','NOTE','WORK','REASON','PROJECT_NAME')
 organization=first(row,'VENDOR_NAME','AWARDED_TO','SUPPLIER_NAME','CLIENT_DIVISION',
                    'DEVELOPER_NAME','OWNER_NAME')
 status=first(row,'STATUS','CONTRACT_STATUS','APPLICATION_STATUS','CURRENT_STATUS',
              'LATEST_MILESTONE','RESTRICTION_TYPE','ROAD_RESTRICTION_TYPE')
 address=first(row,'ADDRESS','FULL_ADDRESS','SITE_ADDRESS','LOCATION','MAIN_ROAD','STREET_NAME')
 published_date=first(row,'CLOSING_DATE','CLOSE_DATE','DATE_AWARDED','AWARD_DATE',
                      'APPLICATION_DATE','SUBMITTED_DATE','START_DATE_TIME','DATE')
 value=first(row,'CONTRACT_AMOUNT','AMOUNT','AWARD_AMOUNT','PROJECT_VALUE','ESTIMATED_VALUE')
 kind=TYPES[sid]
 notes=('Publication change only; solicitation must be checked for live eligibility and close date.'
        if sid=='toronto_open_solicitations' else
        'Award records describe past purchasing decisions; not an open tender.'
        if sid in ('toronto_awarded_contracts','toronto_noncompetitive_contracts') else
        'Project/application evidence only; stages and project-to-application relationships need verification.'
        if sid.startswith('toronto_development') else
        'Road restriction may be maintenance, construction, emergency or event; not proof of a new contract.')
 return {
  'observed_at':change['observed_at'],'source_id':sid,
  'record_key':change['record_key'],'source_change':change['change_type'],
  'signal_type':kind,
  'relevant_provider_categories':categories(' '.join([description,status])),
  'published_date':published_date,'published_status':status,
  'organization':organization,'description':description[:700],
  'address_or_road':address[:240],'published_value':value,
  'source_url':change['source_url'],
  'qualification':'REQUIRES_INDEPENDENT_REVIEW',
  'notes':notes,
 }

def extract(db,limit=2000):
 db.row_factory=sqlite3.Row
 changes=db.execute("""SELECT id,source_id,record_key,observed_at,change_type,source_url,new_hash
 FROM changes ORDER BY id DESC LIMIT ?""",(limit,)).fetchall()
 results=[]
 for item in changes:
  change=dict(item)
  record=db.execute("""SELECT json FROM versions
    WHERE source_id=? AND record_key=? AND hash=? AND observed_at<=?
    ORDER BY id DESC LIMIT 1""",
    (change['source_id'],change['record_key'],change['new_hash'],change['observed_at'])).fetchone()
  if record is None:continue
  try:row=json.loads(record['json'])
  except (TypeError,ValueError):continue
  if not isinstance(row,dict):continue
  candidate=signal(change,row)
  if candidate:results.append(candidate)
 return results

def run():
 database=DATA/'toronto_priority_sources.sqlite'
 if not database.is_file():
  raise RuntimeError('Toronto public record archive missing; signals are not available')
 db=sqlite3.connect('file:'+database.resolve().as_posix()+'?mode=ro',uri=True)
 try:
  results=extract(db)
 finally:db.close()
 OUTPUT.parent.mkdir(exist_ok=True)
 temp=OUTPUT.with_suffix('.csv.tmp')
 with temp.open('w',encoding='utf-8-sig',newline='') as file:
  writer=csv.DictWriter(file,fieldnames=FIELDS,extrasaction='ignore')
  writer.writeheader()
  writer.writerows(results)
 temp.replace(OUTPUT)
 print('Toronto research signals:',len(results),'post-baseline source changes; all require independent qualification')
if __name__=='__main__':run()
