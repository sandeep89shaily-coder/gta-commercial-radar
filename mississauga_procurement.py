"""Mississauga public procurement monitoring during bids&tenders -> Bonfire transition.

Only reads publicly visible HTML. No login, gated documents, vendor account,
payment, browser automation or reverse-engineered private APIs. Baselines and
page changes are NOT automatically qualified open opportunities.
"""
from __future__ import annotations
import hashlib, json, re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from radar import Http
from toronto_public_records import setup, persist

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
DB=DATA/'mississauga_procurement_sources.sqlite'
SOURCES=(
 {'id':'mississauga_bidsandtenders_legacy','department':'Purchasing & Finance',
  'url':'https://mississauga.bidsandtenders.ca/Module/Tenders/en/Home/BidsHomepage',
  'host':'mississauga.bidsandtenders.ca','kind':'legacy'},
 {'id':'mississauga_bonfire_public','department':'Purchasing & Finance',
  'url':'https://mississauga.bonfirehub.ca/portal/?tab=openOpportunities',
  'host':'mississauga.bonfirehub.ca','kind':'new'},
)
MAX_HTML=3*1024*1024
BID_PATTERN=re.compile(r'\b(PRC[\s-]?\d{4,7})\b',re.I)

def stamp():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def compact(text):return ' '.join(str(text or '').split())

def valid(url,host):
 parsed=urlparse(url)
 return parsed.scheme=='https' and parsed.hostname==host and not parsed.username and not parsed.password

def parse_legacy(html,url):
 """Extract only public bid detail links with an official PRC identifier."""
 soup=BeautifulSoup(html,'html.parser')
 extracted={}
 host='mississauga.bidsandtenders.ca'
 for anchor in soup.select('a[href]'):
  detail=urljoin(url,str(anchor.get('href') or ''))
  if not valid(detail,host) or '/tender/detail/' not in urlparse(detail).path.lower():
   continue
  label=compact(anchor.get_text(' ',strip=True))
  row=anchor.find_parent('tr')
  context=compact(row.get_text(' ',strip=True))[:1600] if row else label
  match=BID_PATTERN.search(label) or BID_PATTERN.search(context)
  if match is None:continue
  number=re.sub(r'[\s-]','',match.group(1)).upper()
  if number=='':continue
  title=re.sub(r'^\s*(?:bid\s+details?\s*[-:]\s*)','',label,flags=re.I)
  if len(title)<len(number)+5:
   title=context[:350]
  if not number in title.upper():title=number+' — '+title
  status_match=re.search(r'\b(Open|Closed|Awarded|Cancelled|Canceled)\b',context,re.I)
  status=status_match.group(1).upper() if status_match else 'UNKNOWN'
  record={'BID_NUMBER':number,'TITLE':title[:380],'STATUS':status,
          'PUBLIC_LISTING_TEXT':context[:1200],'DETAIL_URL':detail,
          'EVIDENCE_URL':url,'OBSERVATION_SCOPE':'PUBLIC_LISTING_ONLY'}
  if number not in extracted or len(record['PUBLIC_LISTING_TEXT'])>len(extracted[number]['PUBLIC_LISTING_TEXT']):
   extracted[number]=record
 return list(extracted.values())

def setup_monitors(db):
 setup(db)
 db.executescript("""CREATE TABLE IF NOT EXISTS public_pages(
  source_id TEXT PRIMARY KEY,url TEXT,last_checked TEXT,last_hash TEXT,
  page_preview TEXT,parsed_bid_count INTEGER DEFAULT 0,status TEXT);
 CREATE TABLE IF NOT EXISTS public_page_versions(
  id INTEGER PRIMARY KEY,source_id TEXT,observed_at TEXT,content_hash TEXT,
  parsed_bid_count INTEGER,preview TEXT,UNIQUE(source_id,content_hash));""")
 db.commit()

def monitor_page(db,spec,html,when,parsed=0):
 soup=BeautifulSoup(html,'html.parser')
 for node in soup(['script','style','noscript']):node.decompose()
 preview=compact(soup.get_text(' ',strip=True))[:2500]
 if not preview:raise ValueError('No public content to monitor')
 key=hashlib.sha256(preview.encode('utf-8')).hexdigest()
 sid=spec['id']
 prior=db.execute('SELECT last_hash FROM public_pages WHERE source_id=?',(sid,)).fetchone()
 changed=not prior or prior[0]!=key
 status='PUBLIC_BIDS_PARSED' if parsed else 'PUBLIC_PAGE_ONLY'
 with db:
  db.execute("""INSERT INTO public_pages(source_id,url,last_checked,last_hash,page_preview,parsed_bid_count,status)
    VALUES(?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET
    last_checked=excluded.last_checked,last_hash=excluded.last_hash,
    page_preview=excluded.page_preview,parsed_bid_count=excluded.parsed_bid_count,
    status=excluded.status""",(sid,spec['url'],when,key,preview,parsed,status))
  if changed:
   db.execute("""INSERT OR IGNORE INTO public_page_versions(
    source_id,observed_at,content_hash,parsed_bid_count,preview) VALUES(?,?,?,?,?)""",
    (sid,when,key,parsed,preview))
 return status,changed

def collect(http,source):
 url=source['url']
 if not valid(url,source['host']):raise ValueError('Procurement URL outside verified public host')
 response=http.get(url,timeout=(12,60),retries=2)
 payload=response.content
 if not payload or len(payload)>MAX_HTML:raise ValueError('Procurement page exceeds safe size limits or empty')
 content_type=str(response.headers.get('Content-Type') or '').lower()
 if content_type and 'html' not in content_type:
  raise ValueError('Expected public HTML procurement page')
 html=response.text
 rows=parse_legacy(html,url) if source['kind']=='legacy' else []
 return html,rows

def run():
 DATA.mkdir(exist_ok=True)
 db=sqlite3.connect(DB)
 setup_monitors(db)
 failures=0
 http=Http()
 try:
  for source in SOURCES:
   observed=stamp()
   try:
    html,rows=collect(http,source)
    state,changed=monitor_page(db,source,html,observed,len(rows))
    if rows:
     meta={'package_id':source['url'],'resource_id':source['url'],
           'resource_url':source['url'],'source_url':source['url']}
     spec={'id':source['id'],'department':source['department'],'keys':('BID_NUMBER',)}
     result=persist(db,spec,rows,meta,observed)
     print('Mississauga procurement:',source['id'],result['status'],len(rows),
           'public bid listing observations',flush=True)
    else:
     print('Mississauga procurement:',source['id'],state,
           'no structured bid records extracted; page change=',changed,flush=True)
   except Exception as exc:
    failures+=1
    with db:
     db.execute('INSERT INTO runs(source_id,observed_at,status,fetched,created,updated,detail) VALUES(?,?,?,?,?,?,?)',
                (source['id'],observed,'ERROR',0,0,0,str(exc)[:500]))
    print('Mississauga procurement ERROR:',source['id'],str(exc)[:250],file=sys.stderr,flush=True)
 finally:db.close()
 return 1 if failures else 0

if __name__=='__main__':raise SystemExit(run())
