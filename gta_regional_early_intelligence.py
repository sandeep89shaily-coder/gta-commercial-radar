"""Nine-authority regional early-intelligence collector.

Read-only official HTML project indexes. Preserves baselines, source identity,
access failures, project/policy distinctions. No AI, bypass or invented dates.
"""
from __future__ import annotations
import csv,datetime as dt,hashlib,json,re,socket
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from robots_policy import evaluate
from toronto_pdf_download import public_dns

SOURCES={
 "Toronto":{"url":"https://www.toronto.ca/business-economy/doing-business-with-the-city/upcoming-capital-projects/","kind":"CAPITAL_PIPELINE"},
 "Hamilton":{"url":"https://www.hamilton.ca/environmental-assessments/york-valley-road-hd016-booster-pumping-station-capacity-upgrades","kind":"ENVIRONMENTAL_ASSESSMENT"},
 "York":{"url":"https://www.york.ca/environment/water-and-wastewater/water-and-wastewater-construction-projects","kind":"INFRASTRUCTURE_INDEX"},
 "Peel":{"url":"https://peelregion.ca/construction/environmental-assessments","kind":"ENVIRONMENTAL_ASSESSMENT_INDEX"},
 "Halton":{"url":"https://www.halton.ca/for-residents/infrastructure-and-growth/road-water-wastewater-construction","kind":"INFRASTRUCTURE_INDEX"},
 "Durham":{"url":"https://www.durham.ca/news/posts/notice-of-ajax-water-supply-plant-expansion-project-public-information-centre/","kind":"ENVIRONMENTAL_ASSESSMENT"},
 "Waterloo":{"url":"https://www.regionofwaterloo.ca/programs-and-services/roads-and-transportation/road-construction/","kind":"INFRASTRUCTURE_INDEX"},
 "Niagara":{"url":"https://www.niagararegion.ca/projects/water-wastewater-master-servicing-plan-update/default.aspx","kind":"MASTER_SERVICING_POLICY"},
 "Simcoe":{"url":"https://simcoe.ca/services/planning/amendments-and-current-applications/","kind":"OFFICIAL_PLAN_APPLICATIONS"}
}
AGENT="GTARadarRegionalEarlyIntelligence/1.0"
STATUS="GTA_RADAR_REGIONAL_EARLY_SOURCE_STATUS.json"
LEDGER="GTA_RADAR_REGIONAL_EARLY_FIRST_SEEN.json"
ALL="GTA_RADAR_REGIONAL_EARLY_RECORDS.csv"
CHANGES="GTA_RADAR_REGIONAL_EARLY_NEW_OR_CHANGED.csv"
FIELDS=("record_id","authority","signal_type","project_title","source_url","official_index_url",
        "application_id","stage_hint","published_date","published_date_basis",
        "first_seen_local","observation","verification_required")
KEYWORDS=re.compile(r"\b(?:watermain|wastewater|sewage|sewer|reservoir|pumping|treatment|trunk|rehabilitation|"
    r"improvement|expansion|capital|storage|infrastructure|station|environmental assessment|"
    r"road|bridge|intersection|industrial|employment|development|amendment|planning|"
    r"construction|servicing|tender|procurement|transit|facility|plant)\b",re.I)
NOISE=re.compile(r"\b(?:accessibility|privacy|terms|cookie|contact us|subscribe|news|footer|faq|"
    r"budget documents|share this|social media|view all|search|home page|back to top)\b",re.I)
FILE_ID=re.compile(r"\b(?:SV-T-\d{4}|43-OP-\d{5,7}|(?:OPA|OZ|ZBA|SPC)\s*[-#:]?\s*\d{2,5}(?:[-/]\d{2,5})?)\b",re.I)
MAX_LINKS=250
MAX_BYTES=3_000_000

def _safe_url(url,index):
 p=urlparse(url);i=urlparse(index)
 # strict source-host-only: independent hosts need their own authorization
 return (p.scheme=="https" and p.hostname==i.hostname and p.port in (None,443)
   and not p.username and not p.password and not p.fragment)

def _fetch(url):
 p=urlparse(url)
 if not _safe_url(url,url) or not public_dns(p.hostname,socket.getaddrinfo):
  raise ValueError("INVALID_PUBLIC_OFFICIAL_HOST")
 s=requests.Session();s.trust_env=False
 s.headers.update({"User-Agent":AGENT,"Accept":"text/html"})
 try:
  yes,reason=evaluate(s,url,AGENT,timeout=8)
  if not yes:raise ValueError("POLICY_DENIED:"+reason)
  with s.get(url,timeout=(6,17),stream=True,allow_redirects=False) as resp:
   if resp.status_code!=200 or resp.url!=url:
    raise ValueError("HTTP_"+str(resp.status_code)+"_OR_REDIRECT")
   if "html" not in resp.headers.get("Content-Type","").lower():
    raise ValueError("NON_HTML_OFFICIAL_INDEX")
   chunks=bytearray()
   for part in resp.iter_content(65536):
    chunks.extend(part)
    if len(chunks)>MAX_BYTES:raise ValueError("INDEX_TOO_LARGE")
  return chunks.decode("utf-8","replace")
 finally:s.close()

def _clean(x):return re.sub(r"\s+"," ",str(x or "")).strip()
def _stage(value):
 s=value.casefold()
 if re.search(r"\b(?:completed|complete)\b",s):return "COMPLETED_REVIEW"
 if re.search(r"\b(?:under construction|construction)\b",s):return "CONSTRUCTION_MAY_ALREADY_BE_UNDERWAY"
 if re.search(r"\b(?:design|preliminary design)\b",s):return "DESIGN_REVIEW"
 if re.search(r"\b(?:environmental assessment|assessment|study|consultation)\b",s):return "ASSESSMENT_OR_STUDY"
 if re.search(r"\b(?:proposed|amendment|application)\b",s):return "PROPOSED_OR_APPLICATION_REVIEW"
 return "STAGE_NOT_ESTABLISHED"

def _candidate(authority,kind,index,title,url,context=""):
 title=_clean(title)
 if len(title)<13 or len(title)>220 or NOISE.search(title) or not KEYWORDS.search(title):
  return None
 if not _safe_url(url,index):return None
 # Identifies an official hyperlink or a source-page project entry; not a generic site.
 # No dated evidence is inferred from today's crawl.
 link=url
 identity=link.casefold()+"|"+title.casefold()
 record_id="REGIONAL:"+authority.upper()+":"+hashlib.sha256(identity.encode()).hexdigest()[:20]
 found=FILE_ID.search(title+" "+context)
 return dict(record_id=record_id,authority=authority,signal_type=kind,
    project_title=title,source_url=link,official_index_url=index,
    application_id=found.group() if authority=="Simcoe" and found else "",
    stage_hint=_stage(title+" "+context[:150]),
    published_date="",published_date_basis="NOT_VERIFIED_IN_SOURCE_ENTRY",
    verification_required="Confirm project scope, current stage, dates, procurement status and publisher identity")

def _extract(authority,html,source):
 index=source["url"];kind=source["kind"];soup=BeautifulSoup(html,"html.parser")
 main=soup.find("main") or soup.find(id="main-content") or soup
 candidates={}
 # A named official project link is evidence of a project, not an active contract.
 for a in main.find_all("a",href=True):
  title=_clean(a.get_text(" ",strip=True))
  link=urljoin(index,a["href"])
  if not link.startswith("https://") or not _safe_url(link,index):continue
  if urlparse(link).path==urlparse(index).path:continue
  row=_candidate(authority,kind,index,title,link)
  if row:candidates[row["record_id"]]=row
  if len(candidates)>=MAX_LINKS:break
 # Specific standalone index sections: the published table explicitly has
 # Project / Where / Current status columns. Never count a generic page heading.
 if authority=="Waterloo":
  for table in main.find_all("table"):
   headers=_clean(table.find("tr").get_text(" ",strip=True)).casefold() if table.find("tr") else ""
   if not all(h in headers for h in ("project","status")):continue
   for tr in table.find_all("tr")[1:]:
    cells=tr.find_all("td")
    if len(cells)<3:continue
    title=_clean(cells[0].get_text(" ",strip=True))
    where=_clean(cells[1].get_text(" ",strip=True))
    status=_clean(cells[2].get_text(" ",strip=True))
    link=index+"#regional-project-"+hashlib.sha256((title+"|"+where).encode()).hexdigest()[:12]
    # Fragment is local only and not proof of a direct official deep link.
    row=_candidate(authority,kind,index,title,index,where+" "+status)
    if row:
     row["record_id"]="REGIONAL:WATERLOO:"+hashlib.sha256((title+"|"+where).encode()).hexdigest()[:20]
     row["stage_hint"]=_stage(status)
     row["verification_required"]+="; index-table row has no separately verified project deep link"
     candidates[row["record_id"]]=row
 # Single-project authority pages are a baseline watch on a known official project.
 if kind in ("ENVIRONMENTAL_ASSESSMENT","MASTER_SERVICING_POLICY"):
  heading=main.find("h1")
  if heading:
   title=_clean(heading.get_text(" ",strip=True))
   row=_candidate(authority,kind,index,title,index)
   if row:candidates[row["record_id"]]=row
 return list(candidates.values())

def _write(path,rows):
 with path.open("w",encoding="utf-8-sig",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore");writer.writeheader()
  for row in rows:
   writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v)
      for k,v in row.items() if k in FIELDS})

def run(results,*,today=None,sources=None,fetcher=None):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 day=(today or dt.date.today()).isoformat()
 catalog=sources if sources is not None else SOURCES
 ledger_path=root/LEDGER
 prior=json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {"schema":1,"seen":{}}
 if prior.get("schema")!=1:raise ValueError("UNKNOWN_REGIONAL_FIRST_SEEN_SCHEMA")
 old=prior["seen"];updated=dict(old);all_rows=[];changed=[];status=[]
 for authority,source in catalog.items():
  state={"authority":authority,"source_url":source["url"],"source_type":source["kind"],
         "status":"FAILED","records":0,"new_or_changed":0,
         "automated_application_count":0,"qualified_sales_leads":0}
  try:
   html=(fetcher or _fetch)(source["url"])
   rows=_extract(authority,html,source)
   # zero candidates is not a working project collector.
   state["status"]="BASELINE_COMPLETE" if not any(
     k.startswith("REGIONAL:"+authority.upper()+":") for k in old) else "COLLECTED"
   if not rows:state["status"]="INDEX_FETCHED_NO_IDENTIFIABLE_PROJECTS"
   baseline=not any(k.startswith("REGIONAL:"+authority.upper()+":") for k in old)
   for row in sorted(rows,key=lambda x:x["record_id"]):
    identity=row["record_id"]
    digest=hashlib.sha256(json.dumps({k:row[k] for k in (
      "project_title","source_url","stage_hint","application_id","signal_type")},
      sort_keys=True).encode()).hexdigest()
    before=old.get(identity)
    observation="INITIAL_BASELINE" if baseline else (
      "FIRST_OBSERVED" if before is None else
      "RECORD_CHANGED" if before["digest"]!=digest else "UNCHANGED")
    row.update(first_seen_local=before["first_seen_local"] if before else day,
               observation=observation)
    all_rows.append(row)
    if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):changed.append(row)
    updated[identity]={"digest":digest,"first_seen_local":row["first_seen_local"]}
   state.update(records=len(rows),new_or_changed=sum(x["authority"]==authority for x in changed))
  except Exception as err:
   state["error"]=type(err).__name__+":"+str(err)[:180]
  status.append(state)
 _write(root/ALL,all_rows);_write(root/CHANGES,changed)
 if updated!=old:
  tmp=ledger_path.with_suffix(".tmp")
  tmp.write_text(json.dumps({"schema":1,"seen":updated},indent=2),encoding="utf-8")
  tmp.replace(ledger_path)
 report={"authorities_configured":len(catalog),
    "authorities_with_records":sum(x["records"]>0 for x in status),
    "authorities_failed":sum(x["status"]=="FAILED" for x in status),
    "records":len(all_rows),"new_or_changed":len(changed),
    "verified_commercial_opportunities":0,"paid_ai_calls":0,
    "source_status":status,
    "warning":"These are official regional project/policy signals only. Baseline is not a new lead; records do not establish current procurement, original publication date, citywide completeness or sale-ready contacts."}
 (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
 return report
