"""Peel pilot: conservative, separately-stored official public HTML observations.
Does not touch radar.sqlite or promote historic first-seen records to fresh leads.
"""
import csv, hashlib, json, re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
SOURCES={
 'caledon_development_register': {'name':'Caledon current development applications','url':'https://www.caledon.ca/en/town-services/current-applications.aspx','kind':'private_development','selector':'caledon'},
 'peel_flow_projects':{'name':'Peel Flow water and wastewater projects','url':'https://peelregion.ca/construction/watermain-construction/flow-program/flow-program-map','kind':'government_projects','selector':'peel'},
}
CAL_ID=re.compile(r'\b(?:POPA|SPA|RZ|21T|21CDM|PARC|OPA)\s*[-–]?\s*\d{2,4}[-–]\d{2,6}[A-Z]?\b',re.I)
PEEL_ID=re.compile(r'\b(?:project\s*)?(\d{2}[-–]\d{3,5}(?:\s*[A-Z]\d?)?)\b',re.I)

def normalize(s): return ' '.join((s or '').split())
def stable(s):return hashlib.sha256(s.encode()).hexdigest()[:22]
def parse_caledon(html,base):
 soup=BeautifulSoup(html,'html.parser'); out={}
 for tag in soup.select('li, p, a, h3, h4, h5'):
  text=normalize(tag.get_text(' ',strip=True))
  ids=CAL_ID.findall(text)
  if not ids or len(text)>380:continue
  ident=';'.join(sorted({normalize(i).upper() for i in ids}))
  # Only application-specific entries; broad policy reviews retained but not sold automatically.
  k=stable(ident+'|'+text.lower()) if len(ident)<3 else ident
  link=tag.get('href') if tag.name=='a' else None
  a=tag.find('a',href=True)
  if a: link=a.get('href')
  url=urljoin(base,link) if link else base
  if not url.startswith('https://www.caledon.ca/'):url=base
  if k not in out or len(text)>len(out[k]['title']):out[k]={'record_key':k,'title':text,'url':url,'event_date':'','date_basis':'NO_SOURCE_DATE'}
 return list(out.values())
def parse_peel(html,base):
 soup=BeautifulSoup(html,'html.parser');out={}
 for tag in soup.select('li, a, h3, h4, p'):
  title=normalize(tag.get_text(' ',strip=True))
  if len(title)<12 or len(title)>300:continue
  m=PEEL_ID.search(title)
  if not m:continue
  ident=m.group(1).upper().replace('–','-')
  link=tag.get('href') if tag.name=='a' else None
  a=tag.find('a',href=True)
  if a:link=a['href']
  url=urljoin(base,link) if link else base
  if urlparse(url).hostname not in ('peelregion.ca','www.peelregion.ca'):url=base
  k=ident+'|'+stable(title.lower())[:8]
  if k not in out:out[k]={'record_key':k,'title':title,'url':url,'event_date':'','date_basis':'NO_SOURCE_DATE'}
 return list(out.values())

def init(con):
 con.executescript('''CREATE TABLE IF NOT EXISTS observations(source_id TEXT,record_key TEXT,title TEXT,source_url TEXT,event_date TEXT,date_basis TEXT,first_seen TEXT,last_seen TEXT,content_hash TEXT,PRIMARY KEY(source_id,record_key));
 CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,source_id TEXT,started_at TEXT,status TEXT,records_found INTEGER,added INTEGER,changed INTEGER,error TEXT);
 CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,source_id TEXT,record_key TEXT,change_type TEXT,observed_at TEXT,title TEXT,source_url TEXT);
 ''')

def collect(con,source_id,html=None):
 cfg=SOURCES[source_id];now=datetime.now(timezone.utc).isoformat(timespec='seconds')
 try:
  if html is None:
   response=requests.get(cfg['url'],timeout=30,headers={'User-Agent':'GTACommercialRadar/PeelPilot (public source audit; responsible access)','Accept':'text/html'})
   response.raise_for_status();html=response.text
  rows=(parse_caledon if cfg['selector']=='caledon' else parse_peel)(html,cfg['url'])
  if not rows:raise ValueError('No recognizable public records; source schema may have changed; existing data preserved')
  prior=con.execute('SELECT count(*) FROM observations WHERE source_id=?',(source_id,)).fetchone()[0]
  new=changed=0
  for r in rows:
   fingerprint=stable(r['title']+'|'+r['url'])
   old=con.execute('SELECT content_hash FROM observations WHERE source_id=? AND record_key=?',(source_id,r['record_key'])).fetchone()
   if not old:
    new+=1
    con.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)',(source_id,r['record_key'],r['title'],r['url'],r['event_date'],r['date_basis'],now,now,fingerprint))
    if prior:con.execute('INSERT INTO events(source_id,record_key,change_type,observed_at,title,source_url) VALUES (?,?,?,?,?,?)',(source_id,r['record_key'],'NEWLY_OBSERVED',now,r['title'],r['url']))
   else:
    if old[0]!=fingerprint:
     changed+=1
     con.execute('INSERT INTO events(source_id,record_key,change_type,observed_at,title,source_url) VALUES (?,?,?,?,?,?)',(source_id,r['record_key'],'UPDATED',now,r['title'],r['url']))
    con.execute('UPDATE observations SET title=?,source_url=?,last_seen=?,content_hash=? WHERE source_id=? AND record_key=?',(r['title'],r['url'],now,fingerprint,source_id,r['record_key']))
  con.execute('INSERT INTO runs(source_id,started_at,status,records_found,added,changed,error) VALUES (?,?,?,?,?,?,?)',(source_id,now,'OK_BASELINE' if not prior else 'OK',len(rows),new,changed,''));con.commit()
  return source_id,'OK_BASELINE' if not prior else 'OK',len(rows),new,changed
 except Exception as e:
  con.execute('INSERT INTO runs(source_id,started_at,status,records_found,added,changed,error) VALUES (?,?,?,?,?,?,?)',(source_id,now,'ERROR',0,0,0,str(e)[:500]));con.commit()
  return source_id,'ERROR',0,0,str(e)[:170]

def export(con):
 DATA.mkdir(exist_ok=True)
 for name,sql,cols in [
 ('peel_pilot_observations.csv','SELECT source_id,record_key,title,source_url,event_date,date_basis,first_seen,last_seen FROM observations ORDER BY source_id,record_key',['source_id','record_key','title','source_url','event_date','date_basis','first_seen','last_seen']),
 ('peel_pilot_changes_REVIEW_ONLY.csv','SELECT source_id,record_key,change_type,observed_at,title,source_url FROM events ORDER BY id DESC',['source_id','record_key','change_type','observed_at','title','source_url']),
 ('peel_pilot_runs.csv','SELECT source_id,started_at,status,records_found,added,changed,error FROM runs ORDER BY id DESC',['source_id','started_at','status','records_found','added','changed','error'])]:
  with (DATA/name).open('w',newline='',encoding='utf-8-sig') as f:
   w=csv.writer(f);w.writerow(cols);w.writerows(con.execute(sql))

def main():
 DATA.mkdir(exist_ok=True)
 with sqlite3.connect(DATA/'peel_pilot.sqlite') as con:
  init(con)
  for sid in SOURCES:
   result=collect(con,sid);print('%s: %s; records=%s new=%s changed=%s'%result,flush=True)
  export(con)
 print('Peel pilot reports in data folder. These are source observations, not verified commercial leads.')
if __name__=='__main__':main()
