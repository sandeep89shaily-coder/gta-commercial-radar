"""Public early-signal monitoring; retains dates actually observed, never invents posting dates."""
from __future__ import annotations
import datetime as dt, hashlib, html, json, re, sqlite3
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.request import Request,urlopen

FEEDS={
 "brampton_planning":"https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/",
 "brampton_preplanning":"https://letsconnect.brampton.ca/yourcityplans",
 "burlington_agendas":"https://www.burlington.ca/en/council-and-city-administration/agendas-and-minutes.aspx",
 "ieso_connections":"https://www.ieso.ca/en/Sector-Participants/Connection-Process/Application-Status",
 "ero_notices":"https://ero.ontario.ca/search",
}
HOSTS={urlparse(v).hostname for v in FEEDS.values()}
RULE=re.compile(r"(?:agenda|planning|development|application|report|project|connection|notice|permit|industrial|proposal|environment)",re.I)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.href=None;self.label=[]
 def handle_starttag(self,tag,attrs):
  if tag=="a":
   self.href=dict(attrs).get("href");self.label=[]
 def handle_data(self,data):
  if self.href is not None:self.label.append(data)
 def handle_endtag(self,tag):
  if tag=="a" and self.href:
   self.links.append((self.href," ".join(self.label).strip()))
   self.href=None;self.label=[]
def fetch(url):
 req=Request(url,headers={"User-Agent":"GTARadarPublicResearch/1.0"})
 with urlopen(req,timeout=15) as response:
  if response.status!=200:raise ValueError("HTTP_STATUS")
  body=response.read(1_000_001)
  if len(body)>1_000_000:raise ValueError("BODY_TOO_LARGE")
 return body.decode("utf-8","replace")
def collect(root,transport=None,now=None):
 root=Path(root);root.mkdir(parents=True,exist_ok=True)
 db=sqlite3.connect(root/"RADAR_EARLY_FEED_LEDGER.sqlite")
 db.execute("CREATE TABLE IF NOT EXISTS links (id TEXT PRIMARY KEY, feed TEXT, url TEXT, title TEXT, first_seen_utc TEXT)")
 observed=(now or dt.datetime.now(dt.timezone.utc)).isoformat()
 out=[]
 for feed,url in FEEDS.items():
  try:
   markup=(transport or fetch)(url)
   parser=Parser();parser.feed(markup)
   matched=0
   for href,label in parser.links:
    absolute=urljoin(url,html.unescape(href))
    parsed=urlparse(absolute)
    if parsed.scheme!="https" or not parsed.hostname or not (
      parsed.hostname in HOSTS or parsed.hostname.endswith(".escribemeetings.com") or
      parsed.hostname.endswith(".burlington.ca") or parsed.hostname.endswith(".brampton.ca")
    ):continue
    if not RULE.search(label+" "+parsed.path):continue
    identity=hashlib.sha256((feed+"|"+absolute).encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO links VALUES (?,?,?,?,?)",
               (identity,feed,absolute,label[:250],observed));matched+=1
   out.append({"feed":feed,"status":"INDEX_FETCHED","candidate_links":matched,
               "source_url":url,"publication_date_verified":False})
  except Exception as exc:
   out.append({"feed":feed,"status":"FETCH_FAILED","error_type":type(exc).__name__,"source_url":url})
 db.commit()
 sample=[dict(feed=r[0],url=r[1],title=r[2],first_seen_utc=r[3],
    publication_date_verified=False,work_package_verified=False)
    for r in db.execute("SELECT feed,url,title,first_seen_utc FROM links ORDER BY first_seen_utc DESC LIMIT 250")]
 db.close()
 result={"audited_at_utc":observed,"feeds":out,"candidate_links":sample,
         "verified_buyers":0,"verified_open_work_packages":0,
         "warning":"Index monitoring is NOT confirmed project publication or an available contract"}
 (root/"EARLY_SIGNAL_FEED_AUDIT.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
 return result
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--out",required=True)
 a=p.parse_args();r=collect(a.out)
 print(json.dumps({"sources_checked":len(r["feeds"]),"fetched":sum(x["status"]=="INDEX_FETCHED" for x in r["feeds"])},indent=2))
