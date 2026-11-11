"""Policy-aware recovery of *exact* official Burlington/Vaughan planning file IDs.

This is a bounded addition to the existing Radar run. If publisher policies
deny the source, it reports blocked with zero records. Kitchener, Richmond Hill
and Newmarket are audited against their existing GIS/authorized-export stages;
manual exports never count as automatic coverage.
"""
from __future__ import annotations
import csv,datetime as dt,hashlib,json,re
from pathlib import Path
from urllib.parse import urlparse,urljoin
from bs4 import BeautifulSoup
from gta_regional_early_intelligence import _fetch as fetch_official_html
from gta_burlington_official_pages import _parse as parse_burlington
from gta_vaughan_official_notices import parse as parse_vaughan,SOURCE as VAUGHAN
from gta_early_applications import SOURCES

BURLINGTON_INDEX=SOURCES["Burlington"]
GIS="GTA_RADAR_BURLINGTON_GIS_PROJECTS.csv"
OUTPUT="GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv"
CHANGES="GTA_RADAR_FIVE_CITY_OFFICIAL_NEW_OR_CHANGED.csv"
STATUS="GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json"
LEDGER="GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json"
MAX_BURLINGTON_PAGES=16
FIELDS=("project_id","city","application_id","project_title","address","description",
    "current_status","source_url","record_source_url","source_record_date",
    "date_basis","first_seen_local","observation","provenance",
    "commercial_fit","verification_required")
CITIES=("Burlington","Vaughan","Kitchener","Richmond Hill","Newmarket")
FILE_ID=re.compile(r"(?:^|[^A-Za-z0-9])(?:505|510|520|525|535)-\d{1,4}[/\-]\d{2}(?!\d)",re.I)
CLOSED=re.compile(r"\b(?:refused|withdrawn|closed|cancelled|canceled)\b",re.I)
COMMERCIAL=re.compile(r"\b(?:commercial|industrial|warehouse|retail|office|hotel|"
       r"logistics|storage|factory|manufactur\w*|restaurant|mixed.use|"
       r"employment|distribution|business|medical|data.cent(?:er|re))\b",re.I)

def _text(x):
 return " ".join(str(x or "").split()).strip()

def _valid_burlington(url):
 try:
  p=urlparse(url)
  if (p.scheme!="https" or p.hostname not in ("www.burlington.ca","burlington.ca")
      or p.query or p.fragment or p.username or p.password or p.port not in (None,443)):
   return False
  legacy=(p.path.startswith("/en/news/current-development-projects/") and
          p.path.endswith(".aspx"))
  # Burlington moved from /en/news/.../*.aspx to canonical project posts.
  # Never treat unrelated news, press releases, or the feed index as projects.
  prefix="/news-and-notices/posts/current-development-projects/"
  slug=p.path[len(prefix):] if p.path.startswith(prefix) else ""
  current=bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*/",slug))
  return legacy or current
 except ValueError:return False

def _read(path):
 if not path.is_file():return []
 with path.open(encoding="utf-8-sig",newline="") as f:
  return list(csv.DictReader(f))

def _json(path):
 try:return json.loads(path.read_text(encoding="utf-8"))
 except (ValueError,OSError):return {}

def _write(path,rows):
 with path.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore");w.writeheader()
  for row in rows:
   w.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v)
               for k,v in row.items() if k in FIELDS})

def _burlington_links(root,fetch):
 # Prefer the CURRENT city feed. Older GIS rows may point to legacy .aspx
 # addresses that now 301-redirect (which our fetcher correctly refuses).
 # No redirect following, robots bypass, external links or blind crawling.
 urls=[]
 errors=[]
 try:
  html=fetch(BURLINGTON_INDEX)
  soup=BeautifulSoup(html,"html.parser")
  main=soup.find("main") or soup
  for anchor in main.find_all("a",href=True):
   u=urljoin(BURLINGTON_INDEX,anchor["href"])
   if _valid_burlington(u) and u not in urls:
    urls.append(u)
   if len(urls)>=MAX_BURLINGTON_PAGES:break
 except Exception as error:
  errors.append("INDEX:"+type(error).__name__+":"+str(error)[:140])
 if not urls:
  # Historical GI source can still provide official links on dates when the
  # new index is unavailable; each URL is independently policy-checked.
  for row in _read(root/GIS):
   value=_text(row.get("source_url"))
   if _valid_burlington(value) and value not in urls:
    urls.append(value)
   if len(urls)>=MAX_BURLINGTON_PAGES:break
 return urls[:MAX_BURLINGTON_PAGES],errors

def _burlington_records(html,url):
 parsed=parse_burlington(html,url)
 soup=BeautifulSoup(html,"html.parser")
 main=soup.find("main") or soup
 heading=main.get_text(" ",strip=True)[:1500]
 status_match=re.search(r"\bStatus\s*[-:]\s*(Under Review|Pre.Application|On Hold|Approved|Appealed|Refused|Withdrawn)\b",
    heading,re.I)
 status=_text(status_match.group(1)).upper() if status_match else "NOT_VERIFIED"
 # Capture the bounded Proposed Development section. The legacy saved-page
 # parser can correctly extract file IDs while missing paragraph scope when
 # headings and paragraphs share one <section> wrapper.
 scope=""
 for node in main.find_all(["h2","h3","h4","strong"]):
  if "proposed development" not in _text(node.get_text(" ",strip=True)).lower():
   continue
  parts=[]
  for sibling in node.next_siblings:
   if getattr(sibling,"name",None) in ("h2","h3","h4"):break
   val=_text(sibling.get_text(" ",strip=True) if hasattr(sibling,"get_text") else sibling)
   if val:parts.append(val)
   if len(" ".join(parts))>1100:break
  if not parts and node.parent:
   text=_text(node.parent.get_text(" ",strip=True))
   parts=[re.split(r"\b(?:File Numbers?|Public Meetings?|Planner on File)\b",text,1,re.I)[0]]
  scope=" ".join(parts)[:1000]
  break
 result=[]
 for source in parsed:
  row=dict(project_id=source["project_id"],city="Burlington",
     application_id=source["application_id"],
     project_title=source["project_title"],
     address="",description=scope or _text(source.get("description")) or source["project_title"],
     current_status=status,source_url=url,record_source_url=url,
     source_record_date="",date_basis="NO_VERIFIED_FIRST_PUBLICATION_DATE",
     provenance="LIVE_OFFICIAL_PROJECT_PAGE_EXPLICIT_FILE_NUMBER",
     commercial_fit="TEXT_MATCH_REVIEW_ONLY" if COMMERCIAL.search(
        scope+" "+_text(source.get("description"))+" "+source["project_title"]) else "UNCLASSIFIED",
     verification_required="Verify municipal applicant, project/permit stage, first posting, open work and current buyer")
  result.append(row)
 return result

def _vaughan_records(html):
 rows=[]
 for source in parse_vaughan(html):
  status="NOTICE_PUBLISHED_STAGE_NOT_VERIFIED"
  desc=_text(source.get("description"))
  rows.append(dict(project_id=source["project_id"],city="Vaughan",
    application_id=source["application_id"],project_title="Vaughan public notice",
    address=_text(source.get("address")),description=desc,
    current_status=status,source_url=VAUGHAN,record_source_url=VAUGHAN,
    source_record_date="",date_basis="MEETING_DATE_NOT_FIRST_PUBLICATION",
    provenance="LIVE_OFFICIAL_PUBLIC_NOTICE_EXPLICIT_FILE_NUMBER",
    commercial_fit="TEXT_MATCH_REVIEW_ONLY" if COMMERCIAL.search(desc) else "UNCLASSIFIED",
    verification_required="Confirm notice posting date, application current status, site and owner; minor variance may not mean construction"))
 return rows

def _audit_restricted_sources(root):
 report=_json(root/"GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json")
 york=_json(root/"GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json")
 exports=_json(root/"GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json")
 reports=report.get("source_status",[])+york.get("source_status",[])
 assisted={r.get("city"):r for r in exports.get("source_status",[])}
 results=[]
 for city in ("Kitchener","Richmond Hill","Newmarket"):
  item=next((r for r in reports if r.get("city")==city),{})
  count=int(item.get("application_id_rows",item.get("commercial_candidates",0)) or 0)
  state=_text(item.get("status") or item.get("state")) or "NO_AUTOMATIC_SOURCE_RESULT"
  results.append(dict(city=city,status="SOURCE_REPORT_ONLY_NOT_RECOLLECTED",
    underlying_collector_status=state,
    underlying_candidate_count=count,
    assisted_export_status=assisted.get(city,{}).get("status","MISSING_AUTHORIZED_EXPORT"),
    application_id_rows_this_stage=0,
    automated_source_recovered_this_stage=False,
    access_status="RESTRICTED_OR_UNVERIFIED" if not count else "VERIFY_APPLICATION_LEVEL_COMPLETENESS",
    source_failure=_text(item.get("error"))))
 return results

def run(results,*,today=None,fetcher=None):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 day=(today or dt.date.today()).isoformat()
 fetch=fetcher or fetch_official_html
 old_path=root/LEDGER
 ledger=_json(old_path) if old_path.exists() else {"schema":1,"seen":{}}
 if ledger.get("schema")!=1 or not isinstance(ledger.get("seen"),dict):
  raise ValueError("UNKNOWN_FIVE_CITY_LEDGER")
 original=ledger["seen"];updated=dict(original)
 output=[];changed=[];statuses=[]
 urls,index_errors=_burlington_links(root,fetch)
 burlington_status=dict(city="Burlington",status="NO_OFFICIAL_PROJECT_LINKS",
   links_selected=len(urls),links_parsed=0,failed_links=index_errors,
   application_id_rows_this_stage=0,automated_source_recovered_this_stage=False)
 for url in urls:
  try:
   html=fetch(url) # Per-link robots, DNS and no-redirect check by shared fetcher.
   found=_burlington_records(html,url)
   if not found:
    raise ValueError("NO_EXPLICIT_CITY_FILE_NUMBERS")
   output.extend(found);burlington_status["links_parsed"]+=1
  except Exception as error:
   burlington_status["failed_links"].append({"url":url,
     "error":type(error).__name__+":"+str(error)[:150]})
 if urls and burlington_status["links_parsed"]:
  burlington_status["status"]="PARTIAL_OFFICIAL_PAGE_COLLECTION" if burlington_status["failed_links"] else "OFFICIAL_PAGE_COLLECTION"
 elif burlington_status["failed_links"]:
  burlington_status["status"]="SOURCE_ACCESS_OR_PARSE_BLOCKED"
 burlington_status["application_id_rows_this_stage"]=len([r for r in output if r["city"]=="Burlington"])
 burlington_status["automated_source_recovered_this_stage"]=bool(burlington_status["application_id_rows_this_stage"])
 statuses.append(burlington_status)
 v=dict(city="Vaughan",status="SOURCE_ACCESS_OR_PARSE_BLOCKED",application_id_rows_this_stage=0,
        automated_source_recovered_this_stage=False)
 try:
  body=fetch(VAUGHAN)
  v_rows=_vaughan_records(body)
  output.extend(v_rows)
  v.update(status="OFFICIAL_NOTICE_COLLECTION" if v_rows else "INDEX_FETCHED_NO_FILE_NUMBERS",
           application_id_rows_this_stage=len(v_rows),
           automated_source_recovered_this_stage=bool(v_rows))
 except Exception as error:
  v["error"]=type(error).__name__+":"+str(error)[:160]
 statuses.append(v)
 # A URL or GIS metadata result cannot increase automated application-ID count.
 statuses.extend(_audit_restricted_sources(root))
 # A complete baseline applies per city, preserving any prior successful data
 # if a different city is blocked on the current run.
 unique={}
 conflicted=set()
 conflict_city={}
 for row in output:
  pid=row["project_id"]
  if pid in conflicted:
   continue
  earlier=unique.get(pid)
  if earlier is not None:
   # One application ID can occur on separate project pages or sites.
   # Even if the text happens to match, a different official page does
   # not establish that the projects have the same physical identity.
   if any(earlier.get(k)!=row.get(k) for k in (
       "record_source_url","description","current_status","address")):
    conflicted.add(pid)
    conflict_city[pid]=row["city"]
    unique.pop(pid,None)
   continue
  unique[pid]=row
 # Status counts must reflect only ambiguity-free accepted source rows,
 # not a raw page count which may include conflicting duplicate IDs.
 for item in statuses:
  if item["city"] in ("Burlington","Vaughan"):
   city=item["city"]
   accepted=sum(r["city"]==city for r in unique.values())
   held=sum(c==city for c in conflict_city.values())
   item["application_id_rows_this_stage"]=accepted
   item["automated_source_recovered_this_stage"]=bool(accepted)
   item["identity_conflicts_held"]=held
   if held and item["status"]=="OFFICIAL_PAGE_COLLECTION":
    item["status"]="PARTIAL_OFFICIAL_PAGE_COLLECTION_IDENTITY_HOLD"
   elif held and item["status"]=="OFFICIAL_NOTICE_COLLECTION":
    item["status"]="PARTIAL_OFFICIAL_NOTICE_COLLECTION_IDENTITY_HOLD"
 for row in sorted(unique.values(),key=lambda item:item["project_id"]):
  pid=row["project_id"];city=row["city"]
  fingerprint={k:row[k] for k in ("description","current_status","address","record_source_url")}
  digest=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
  prior=original.get(pid)
  baseline=not any(k.startswith("OFFICIAL_PAGE:"+city.upper()+":")
                   or k.startswith("OFFICIAL_NOTICE:"+city.upper()+":") for k in original)
  if baseline:
   obs="INITIAL_BASELINE"
  elif prior is None:
   # Existing Burlington history was previously under-parsed. On the first
   # post-fix run, old official file numbers become visible in today's fetch.
   # The site doesn't supply a VERIFIED original public posting date.
   # Treat these as historical-source backfill until a human checks the
   # actual notice age; never promote to a newly published project alert.
   obs=("FIRST_OBSERVED_UNDATED_HELD" if
        row.get("date_basis") in ("NO_VERIFIED_FIRST_PUBLICATION_DATE",
                                  "MEETING_DATE_NOT_FIRST_PUBLICATION")
        else "FIRST_OBSERVED")
  else:
   obs="RECORD_CHANGED" if digest!=prior["digest"] else "UNCHANGED"
  row.update(observation=obs,first_seen_local=prior["first_seen_local"] if prior else day)
  if obs in ("FIRST_OBSERVED","RECORD_CHANGED"):changed.append(row)
  updated[pid]={"digest":digest,"first_seen_local":row["first_seen_local"]}
 _write(root/OUTPUT,list(unique.values()))
 _write(root/CHANGES,changed)
 if updated!=original:
  tmp=old_path.with_suffix(".tmp")
  tmp.write_text(json.dumps({"schema":1,"seen":updated},indent=2),encoding="utf-8")
  tmp.replace(old_path)
 report={"status":"COLLECTED" if unique else "NO_AUTOMATIC_RECOVERY",
    "cities_targeted":5,
    "automatic_file_id_rows_this_stage":len(unique),
    "new_or_changed":len(changed),
    "newly_observed_undated_file_ids_held_for_publication_review":sum(
       r["observation"]=="FIRST_OBSERVED_UNDATED_HELD"
       for r in unique.values()),
    "identity_conflicts_held_count":len(conflicted),
    "identity_conflicts_held_ids":sorted(conflicted),
    "automatically_recovered_cities":[r["city"] for r in statuses if r.get("automated_source_recovered_this_stage")],
    "verified_citywide_complete":0,
    "verified_new_commercial_leads":0,
    "source_status":statuses,
    "warning":"Only file IDs read from permitted live official HTML count here. Separate GIS/assisted exports remain independently audited; meeting dates and Radar first-seen dates do not prove original publication, nor do source records prove unawarded work."}
 (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
 return report
