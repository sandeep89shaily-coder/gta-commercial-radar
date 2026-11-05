"""GGH early planning: official municipal application-level HTML collection.

Twelve candidate sources; no invented identifiers or dates. Live policy-aware fetch,
source-by-source baseline and separate review candidates. Never marks an HTML
landing page as verified citywide coverage.
"""
from __future__ import annotations
import csv,datetime as dt,hashlib,json,re,socket
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from robots_policy import evaluate
from toronto_pdf_download import public_dns
from gta_ggh_six_city_sources import (
    SOURCES as SIX_CITY_SOURCES, extract_notice as extract_expanded_notice,
    extract_thorold as extract_expanded_thorold, notice_links as expanded_notice_links,
)

SOURCES={
 "Niagara Falls":"https://webpublic.niagarafalls.ca/Planning/",
 "County of Brant":"https://www.brant.ca/planning-and-development/active-applications/",
 "Peterborough":"https://www.peterborough.ca/business-building-development/planning-building-and-development/planning-and-development-services/current-development-applications/",
 "Pickering":"https://www.pickering.ca/devapp",
 "Orillia":"https://www.orillia.ca/build-and-invest/planning-and-development/current-development-activity/",
 "Barrie":"https://gispublic.barrie.ca/arcgis/rest/services/Public/AnnexedLand_ActiveApplications_WA_Static/MapServer/4"
}
SOURCES.update(SIX_CITY_SOURCES)
AGENT="GTARadarGGHPlanning/1.0"
LEDGER="GTA_RADAR_GGH_EXPANSION_SEEN.json"
STATUS="GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json"
ALL="GTA_RADAR_GGH_EXPANSION_APPLICATIONS.csv"
CHANGES="GTA_RADAR_GGH_EXPANSION_NEW_OR_CHANGED.csv"
FIELDS=("project_id","city","application_id","address","description","application_type",
        "applicant","official_record_url","source_url","source_date","source_date_basis",
        "first_seen_local","observation","commercial_fit","record_evidence",
        "verification_required")
COMMERCIAL=re.compile(r"\b(?:commercial|industrial|warehouse|distribution|factory|retail|office|hotel|"
    r"employment|manufactur\w*|logistics|medical|clinic|hospital|mixed.use|storage|dealership|"
    r"restaurant|institutional|data.cent(?:er|re)|school|automotive|servic\w*)\b",re.I)
NIAGARA=re.compile(r"\b(?:AM-\d{4}-\d{3}|(?:26T|26CD)-\d{4}-\d{3}|OPA-\d{4}-\d{3})\b",re.I)
BRANT=re.compile(r"\b(?:ZBA\d+[-A-Z0-9]*|OPA\d+[-A-Z0-9]*|B\d+-A\d+-\d{2}-[A-Z]+|"
    r"(?:SBA|ZBA|OPA|B|A)\d+[-A-Z0-9]*)\b",re.I)
PETER=re.compile(r"\b(?:SPC\s+\d{2,5}|(?:OPA|ZBA|SUB|CDM)\s*[-#:]?\s*\d{2,6})\b",re.I)
GENERIC=re.compile(r"\b(?:[A-Z]{2,5}\s*[-/]\s*20\d{2}[-/]\d{2,5}|(?:ZBA|OPA|SP|SPC)\s*[-#]?\s*\d{2,6})\b",re.I)
MAX_BYTES=3_000_000

def _clean(s):return re.sub(r"\s+"," ",str(s or "")).strip()
def _safe(url,origin):
 p,o=urlparse(url),urlparse(origin)
 return (p.scheme=="https" and p.hostname==o.hostname and p.port in (None,443)
     and not p.username and not p.password and not p.fragment)

def _fetch(url):
 if not _safe(url,url) or not public_dns(urlparse(url).hostname,socket.getaddrinfo):
  raise ValueError("UNSAFE_OFFICIAL_SOURCE")
 s=requests.Session();s.trust_env=False
 s.headers.update({"User-Agent":AGENT,"Accept":"text/html"})
 try:
  permitted,reason=evaluate(s,url,AGENT,timeout=8)
  if not permitted:raise ValueError("ROBOTS_"+reason)
  with s.get(url,timeout=(6,18),stream=True,allow_redirects=False) as response:
   if response.status_code!=200 or response.url!=url:
    raise ValueError("HTTP_"+str(response.status_code)+"_OR_REDIRECT")
   if "html" not in response.headers.get("Content-Type","").lower():
    raise ValueError("NON_HTML_SOURCE")
   body=bytearray()
   for part in response.iter_content(65536):
    body.extend(part)
    if len(body)>MAX_BYTES:raise ValueError("SOURCE_TOO_LARGE")
  return body.decode("utf-8","replace")
 finally:s.close()

def _record(city,number,address,description,source,*,record_url="",applicant="",kind="",date="",date_basis=""):
 number=_clean(number).upper()
 if not number or len(number)>110 or not any(c.isdigit() for c in number):return None
 address=_clean(address)[:240];description=_clean(description)[:800]
 if len(address)<4 and len(description)<15:return None
 record_url=record_url if record_url and _safe(record_url,source) else source
 identity=city.upper()+":"+re.sub(r"\s+","",number)
 return dict(project_id="GGH:"+identity,city=city,application_id=number,
   address=address,description=description,application_type=_clean(kind)[:160],
   applicant=_clean(applicant)[:160],official_record_url=record_url,
   source_url=source,source_date=_clean(date)[:30],
   source_date_basis=(date_basis if date else "NO_VERIFIED_SOURCE_PUBLICATION_DATE"),
   commercial_fit="COMMERCIAL_TEXT_MATCH_REVIEW" if COMMERCIAL.search(
       description+" "+kind+" "+applicant) else "UNCLASSIFIED_REVIEW",
   record_evidence="OFFICIAL_APPLICATION_NUMBER_AND_CONTEXT",
   verification_required="Confirm filing, stage, source publication date, commercial scope, owner and purchasing authority")

def _niagara(soup,source):
 out=[]
 for tr in soup.select("tr"):
  cells=tr.find_all(["td","th"],recursive=False)
  if len(cells)<3:continue
  number=NIAGARA.search(_clean(cells[0].get_text(" ",strip=True)))
  if not number:continue
  address=_clean(cells[1].get_text(" ",strip=True))
  typ=_clean(cells[2].get_text(" ",strip=True))
  if not address or address.casefold()=="address":continue
  a=cells[0].find("a",href=True) or tr.find("a",href=True)
  link=urljoin(source,a["href"]) if a else source
  row=_record("Niagara Falls",number.group(),address,typ,source,record_url=link,kind=typ)
  if row:out.append(row)
 return out

def _brant(soup,source):
 out=[]
 for tr in soup.select("tr"):
  cells=tr.find_all(["td","th"],recursive=False)
  if len(cells)<4:continue
  number=BRANT.search(_clean(cells[0].get_text(" ",strip=True)))
  if not number:continue
  address=_clean(cells[1].get_text(" ",strip=True))
  kind=_clean(cells[2].get_text(" ",strip=True))
  meeting=_clean(cells[3].get_text(" ",strip=True))
  a=tr.find("a",href=True)
  link=urljoin(source,a["href"]) if a else source
  row=_record("County of Brant",_clean(cells[0].get_text(" ",strip=True)),
      address,kind+"; public meeting "+meeting,source,record_url=link,kind=kind)
  if row:out.append(row)
 return out

def _peterborough(soup,source):
 # File number and owner appear together in a structured individual section.
 # Take the closest preceding heading and bounded following text only.
 out=[]
 for text_node in soup.find_all(string=re.compile(r"\bFile Number\s*:",re.I)):
  container=text_node.parent
  text=_clean(container.get_text(" ",strip=True))
  if len(text)<12:
   parent=container.parent
   text=_clean(parent.get_text(" ",strip=True))[:1400] if parent else text
  match=re.search(r"File Number\s*:\s*("+PETER.pattern[2:-2]+r")",text,re.I)
  if not match:
   match=PETER.search(text.split("File Number",1)[-1][:60])
  if not match:continue
  number=match.group(1) if match.lastindex else match.group(0)
  heading=container.find_previous(["h2","h3","h4"])
  address=_clean(heading.get_text(" ",strip=True)) if heading else ""
  if not address or len(address)>190:continue
  desc=text
  if len(desc)<50:
   block=heading.find_next(["p","div"]) if heading else None
   if block:desc+= " "+_clean(block.get_text(" ",strip=True))
  row=_record("Peterborough",number,address,desc,source)
  if row:out.append(row)
 return out

def _general(city,soup,source):
 # Strict IDs only; no synthesized ID from title, address or ArcGIS object ID.
 out=[]
 for el in soup.find_all(["tr","li","article","h2","h3","h4"]):
  txt=_clean(el.get_text(" ",strip=True))
  if len(txt)<22 or len(txt)>1100:continue
  match=GENERIC.search(txt)
  if not match:continue
  a=el.find("a",href=True)
  link=urljoin(source,a["href"]) if a else source
  row=_record(city,match.group(),txt[:180],txt,source,record_url=link)
  if row:out.append(row)
 return out

def _barrie_gis(url,fetch=None):
 from gta_additional_city_gis import _read_json
 fetch=fetch or _read_json
 meta=fetch(url,{"f":"json"})
 fields={x.get("name") for x in meta.get("fields",[]) if isinstance(x,dict)}
 required={"OBJECTID","FILENO","LOCATION","STATUS","DESCRIPT"}
 if not required.issubset(fields):raise ValueError("BARRIE_GIS_SCHEMA_NOT_VERIFIED")
 rows=[];offset=0;complete=False
 for page in range(16):
  result=fetch(url+"/query",{"f":"json","where":"1=1","returnGeometry":"false",
      "outFields":"OBJECTID,FILENO,LOCATION,STATUS,DESCRIPT,NAME,TYPE,APPLICANT,OWNER",
      "orderByFields":"OBJECTID ASC","resultOffset":str(offset),"resultRecordCount":"500"})
  features=result.get("features")
  if not isinstance(features,list):raise ValueError("BARRIE_GIS_QUERY_NO_FEATURES")
  for feature in features:
   attrs=feature.get("attributes",{}) if isinstance(feature,dict) else {}
   if not isinstance(attrs,dict):continue
   number=_clean(attrs.get("FILENO"))
   if not number or len(number)>110 or not any(x.isdigit() for x in number):continue
   desc=_clean(attrs.get("DESCRIPT")) or _clean(attrs.get("NAME"))
   location=_clean(attrs.get("LOCATION"))
   stage=_clean(attrs.get("STATUS"))
   kind=_clean(attrs.get("TYPE"))
   applicant=_clean(attrs.get("APPLICANT"))
   obj=_record("Barrie",number,location,
       desc+"; stage: "+stage,url,record_url=url,applicant=applicant,kind=kind)
   if obj:rows.append(obj)
  if len(features)<500:
   complete=True;break
  offset+=len(features)
 if not complete:raise ValueError("BARRIE_GIS_INCOMPLETE_PAGINATION")
 return rows

def _extract(city,html,source):
 soup=BeautifulSoup(html,"html.parser")
 if city=="Niagara Falls":rows=_niagara(soup,source)
 elif city=="County of Brant":rows=_brant(soup,source)
 elif city=="Peterborough":rows=_peterborough(soup,source)
 else:rows=_general(city,soup,source)
 merged={}
 for row in rows:
  key=row["project_id"]
  if key in merged:
   old=merged[key]
   if len(row["description"])>len(old["description"]):
    merged[key]=row
  else:merged[key]=row
 return list(merged.values())

def _write(path,rows):
 with path.open("w",encoding="utf-8-sig",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore");writer.writeheader()
  for row in rows:
   writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@"))
     else v) for k,v in row.items() if k in FIELDS})

def run(results,*,today=None,sources=None,fetcher=None):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 today=(today or dt.date.today()).isoformat()
 catalog=sources if sources is not None else SOURCES
 ledger=root/LEDGER
 prior=json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {"schema":1,"seen":{}}
 if prior.get("schema")!=1:raise ValueError("UNKNOWN_EXPANSION_LEDGER")
 old=prior["seen"];seen=dict(old);rows=[];changes=[];statuses=[]
 for city,url in catalog.items():
  item={"city":city,"source_url":url,"state":"FAILED","application_id_rows":0,
        "new_or_changed":0,"commercial_text_matches":0,"source_date_verified_rows":0}
  try:
   if city=="Barrie" and "gispublic.barrie.ca" in url:
    found=_barrie_gis(url)
   else:
    html=(fetcher or _fetch)(url)
    if city in SIX_CITY_SOURCES:
     item["collection_method"]="STRICT_OFFICIAL_NOTICE_FILE_IDS"
     if city=="Thorold":
      found=extract_expanded_thorold(html,url,_record)
     else:
      found=extract_expanded_notice(city,html,url,url,_record)
     targets=expanded_notice_links(html,city,url)
     item["notice_pages_targeted"]=len(targets)
     item["notice_pages_fetched"]=0
     item["notice_page_errors"]=[]
     by_id={x["project_id"]:x for x in found}
     for target in targets:
      try:
       body=(fetcher or _fetch)(target)
       notice_rows=extract_expanded_notice(city,body,url,target,_record)
       for row in notice_rows:
        by_id[row["project_id"]]=row
       item["notice_pages_fetched"]+=1
      except Exception as e:
       item["notice_page_errors"].append({"url":target,
          "error":type(e).__name__+":"+str(e)[:130]})
     found=list(by_id.values())
    else:
     found=_extract(city,html,url)
   baseline=not any(x.startswith("GGH:"+city.upper()+":") for x in old)
   item["state"]=("BASELINE_COMPLETE" if baseline else "COLLECTED") if found else "NO_APPLICATION_ID_ROWS"
   for r in sorted(found,key=lambda r:r["project_id"]):
    key=r["project_id"]
    digest=hashlib.sha256(json.dumps({field:r[field] for field in
       ("application_id","address","description","application_type","applicant")},
       sort_keys=True).encode()).hexdigest()
    prev=old.get(key)
    r["first_seen_local"]=prev["first_seen_local"] if prev else today
    r["observation"]="INITIAL_BASELINE" if baseline else (
      "FIRST_OBSERVED" if not prev else "RECORD_CHANGED" if prev["digest"]!=digest else "UNCHANGED")
    rows.append(r)
    if r["observation"] in ("FIRST_OBSERVED","RECORD_CHANGED"):changes.append(r)
    seen[key]={"digest":digest,"first_seen_local":r["first_seen_local"]}
   item.update(application_id_rows=len(found),
       new_or_changed=sum(r["city"]==city for r in changes),
       commercial_text_matches=sum(r["commercial_fit"]=="COMMERCIAL_TEXT_MATCH_REVIEW" for r in found))
  except Exception as exc:
   item["error"]=type(exc).__name__+":"+str(exc)[:180]
  statuses.append(item)
 _write(root/ALL,rows);_write(root/CHANGES,changes)
 if seen!=old:
  t=ledger.with_suffix(".tmp")
  t.write_text(json.dumps({"schema":1,"seen":seen},indent=2),encoding="utf-8")
  t.replace(ledger)
 report={"cities_configured":len(catalog),"cities_with_application_ids":sum(
    x["application_id_rows"]>0 for x in statuses),"application_id_rows":len(rows),
    "new_or_changed":len(changes),"verified_fresh_commercial_leads":0,
    "citywide_coverage_verified":0,"source_status":statuses,
    "warning":"Only explicitly numbered official notices are application candidates for six new municipalities. Dynamic maps and index-only pages are not accepted as coverage; source publication dates, commercial suitability and citywide completeness not verified."}
 (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
 return report
