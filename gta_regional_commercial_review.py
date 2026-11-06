"""Evidence-gated regional commercial-review queue built from official sources.

Do NOT convert regional index links, historical baselines, construction
activity, source-target-year estimates, or awarded tenders into open contracts.
This stage uses existing data; no network or paid AI calls.
"""
from __future__ import annotations
import csv,datetime as dt,hashlib,json,re
from pathlib import Path
from urllib.parse import urlparse

CAPITAL="GTA_RADAR_TORONTO_CAPITAL_PIPELINE.csv"
DETAILS="GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv"
DOCUMENTS="GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE.csv"
OUTPUT="GTA_RADAR_REGIONAL_COMMERCIAL_REVIEW.csv"
NEW="GTA_RADAR_REGIONAL_COMMERCIAL_CHANGES_TO_REVIEW.csv"
EXCLUDED="GTA_RADAR_REGIONAL_COMMERCIAL_EXCLUDED.csv"
STATUS="GTA_RADAR_REGIONAL_COMMERCIAL_REVIEW_STATUS.json"
COLUMNS=("record_id","source_type","authority","city","project_name","scope_of_work",
 "buyer_organization","project_url","evidence_document_url","document_excerpt",
 "application_id","estimated_contract_value","planned_sourcing_year",
 "planned_award_year","stage_hint","source_date","source_date_basis",
 "first_seen_local","observation","commercial_scope","procurement_gate",
 "priority","rejection_reason","source_verified_as_official",
 "verified_open_tender","verification_required")
CLOSED=re.compile(r"\b(?:awarded|award(?:ed)?\s+to|contract\s+executed|"
                  r"construction\s+(?:completed|finished)|"
                  r"project\s+(?:completed|cancelled|canceled|terminated)|"
                  r"work\s+is\s+complete|permanently\s+closed|"
                  r"no longer proceeding)\b",re.I)
STARTED=re.compile(r"\b(?:construction\s+(?:began|started|is underway|commenced)|"
                   r"under construction|in construction|work\s+(?:has\s+)?commenced)\b",re.I)
PROJECT=re.compile(r"\b(?:construction|building|upgrade|expansion|installation|"
    r"replacement|rehabilitation|new|facility|bridge|sewer|watermain|pumping|"
    r"reservoir|industrial|warehouse|treatment plant|road widening|"
    r"capital works|rail|stormwater|school|hospital|transit)\b",re.I)
LOW_VALUE=re.compile(r"\b(?:policy statement|master (?:plan|servicing study)|"
    r"guideline|regulation only|public consultation only)\b",re.I)

def _read(path):
 if not path.is_file():return []
 with path.open(encoding="utf-8-sig",newline="") as f:
  return list(csv.DictReader(f))

def _text(x):
 return " ".join(str(x or "").split())[:2500]

def _source(url):
 try:
  p=urlparse(url)
  return bool(p.scheme=="https" and p.hostname and p.port in (None,443)
      and not p.username and not p.password)
 except ValueError:return False

def _base(authority,key):
 return ("REGIONAL_REVIEW:"+authority.upper().replace(" ","_")+":"+
         hashlib.sha256(key.encode()).hexdigest()[:24])

def _candidate_capital(row,year):
 url=_text(row.get("source_document_url"))
 title=_text(row.get("project_name_contract"))
 scope=_text(row.get("scope_of_work"))
 if not (_source(url) and title and scope):return None
 target=_text(row.get("target_sourcing_year"))
 priority="MONITOR_PLANNED" if target.isdigit() and int(target)>=year else "RECHECK_HISTORICAL"
 reason="" if priority=="MONITOR_PLANNED" else "PLANNED_SOURCING_YEAR_BEFORE_CURRENT_YEAR_OR_MISSING"
 rejection="EXPLICIT_AWARDED_OR_COMPLETED" if CLOSED.search(title+" "+scope) else reason
 if rejection=="EXPLICIT_AWARDED_OR_COMPLETED":priority="EXCLUDE"
 record=dict(record_id=_base("Toronto",title.casefold()),source_type="TORONTO_CAPITAL_PDF",
  authority="Toronto",city="Toronto",project_name=title,scope_of_work=scope,
  buyer_organization=_text(row.get("project_owner_division")),
  project_url=url,evidence_document_url=url,document_excerpt="",
  application_id="",estimated_contract_value=_text(row.get("estimated_range")),
  planned_sourcing_year=target,planned_award_year=_text(row.get("target_award_year")),
  stage_hint="PLANNED_CAPITAL_PROCUREMENT",
  source_date="",source_date_basis="TARGET_YEAR_IS_NOT_FIRST_PUBLICATION",
  first_seen_local=_text(row.get("first_seen_local")),
  observation=_text(row.get("observation")),
  commercial_scope="POTENTIAL_WORK_SCOPE_REVIEW" if PROJECT.search(scope+" "+title) else "UNCLASSIFIED",
  procurement_gate="OPEN_TENDER_NOT_VERIFIED",
  priority=priority,rejection_reason=rejection,
  source_verified_as_official="OFFICIAL_CITY_CAPITAL_PDF",
  verified_open_tender="false",
  verification_required="Check current City of Toronto tender portal for solicitation, award, contractor, current timing and actual buyer")
 return record

MUNICIPALITIES=("Markham","Vaughan","Richmond Hill","Newmarket","Aurora",
 "East Gwillimbury","Whitchurch-Stouffville","Georgina","King","Pickering",
 "Ajax","Brampton","Mississauga","Caledon","Bolton","Cambridge",
 "Kitchener","Waterloo","Woolwich","Wellesley","North Dumfries",
 "Wil mot","Wil mot")  # Unambiguous titles/official city markers only

def _municipality(title,body):
    """Never guess a municipality from the regional owner's headquarters."""
    title=_text(title)
    body=_text(body)
    # Exact titles with a city are usable; a multi-city project remains blank.
    found=[c for c in MUNICIPALITIES if re.search(r"(?<!\w)"+re.escape(c)+r"(?!\w)",title,re.I)]
    if len(found)==1:return found[0]
    if found:return ""
    found=[c for c in MUNICIPALITIES if re.search(
        r"\b(?:City|Town|Township|Village)\s+of\s+"+re.escape(c)+r"\b",body,re.I)]
    return found[0] if len(found)==1 else ""

def _candidate_detail(row,documents):
 authority=_text(row.get("authority"))
 url=_text(row.get("project_url"))
 title=_text(row.get("project_title"))
 excerpt=_text(row.get("evidence_excerpt"))
 if authority not in ("York","Peel","Waterloo") or not (_source(url) and title and excerpt):
  return None
 pid=_text(row.get("project_id"))
 child=documents.get(pid,{})
 pdf=_text(child.get("document_url"))
 pdf_excerpt=_text(child.get("evidence_excerpt"))
 stage=_text(row.get("stage_evidence"))
 scope=(excerpt+" "+pdf_excerpt).strip()[:2500]
 context=title+" "+scope
 low=bool(LOW_VALUE.search(title)) or not PROJECT.search(context)
 # A historical status does not become a newly open opportunity simply
 # because the page is still hosted. Contradictory language stays for review.
 if CLOSED.search(context):
  priority,why="EXCLUDE","EXPLICIT_AWARDED_OR_COMPLETED"
 elif STARTED.search(context) or stage=="CONSTRUCTION":
  priority,why="RECHECK_IN_PROGRESS","CONSTRUCTION_ALREADY_STARTED_OR_UNCLEAR"
 elif low:
  priority,why="EXCLUDE","NOT_AN_IDENTIFIED_CONSTRUCTION_PROJECT"
 else:priority,why="PROJECT_STAGE_REVIEW",""
 return dict(record_id=_base(authority,url),source_type="REGIONAL_PROJECT_DETAIL",
  authority=authority,city=_municipality(title,scope),project_name=title,scope_of_work=excerpt,
  buyer_organization=authority+" Region",
  project_url=url,evidence_document_url=pdf if _source(pdf) else "",
  document_excerpt=pdf_excerpt if _source(pdf) else "",
  application_id="",estimated_contract_value=_text(row.get("budget_evidence") or child.get("budget_evidence")),
  planned_sourcing_year="",planned_award_year="",stage_hint=stage,
  source_date=_text(row.get("explicit_source_date")),
  source_date_basis=_text(row.get("source_date_basis")) or "UNKNOWN_NOT_ORIGINAL_PUBLICATION",
  first_seen_local=_text(row.get("first_seen_local")),
  observation=_text(row.get("observation")),
  commercial_scope="POTENTIAL_WORK_SCOPE_REVIEW" if not low else "SCOPE_UNCLASSIFIED",
  procurement_gate="OPEN_TENDER_NOT_VERIFIED",
  priority=priority,rejection_reason=why,
  source_verified_as_official=_text(row.get("source_verification")),
  verified_open_tender="false",
  verification_required="Identify exact municipality/location, current package status, tender/award and buyer; do not infer first publication from Radar observation")

def _write(path,rows):
 with path.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=COLUMNS,extrasaction="ignore");w.writeheader()
  for row in rows:
   w.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v)
             for k,v in row.items() if k in COLUMNS})

def run(results,*,today=None):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 year=(today or dt.date.today()).year
 raw_capital=_read(root/CAPITAL)
 raw_details=_read(root/DETAILS)
 raw_docs=_read(root/DOCUMENTS)
 document_by_project={r.get("project_id"):r for r in raw_docs if r.get("project_id")}
 status={"status":"NO_EVIDENCE","source_inputs":{
     CAPITAL:len(raw_capital),DETAILS:len(raw_details),DOCUMENTS:len(raw_docs)},
    "total_evidence_candidates":0,"review_records":0,"new_or_changed_review":0,
    "excluded_or_deferred":0,"verified_open_tenders":0,
    "current_procurement_verified":False,
    "warning":"A city capital pipeline and regional project pages prove proposed/planned work, NOT open contracts. Award checks remain manual. Baselines are not new discoveries."}
 candidates=[r for item in raw_capital if (r:=_candidate_capital(item,year))]
 candidates.extend(r for item in raw_details
                   if (r:=_candidate_detail(item,document_by_project)))
 unique={}
 for row in candidates:
  if row["record_id"] not in unique:unique[row["record_id"]]=row
 # Exclusions and deferred construction projects remain visible with reasons,
 # rather than disappearing from the evidence record.
 records=sorted(unique.values(),key=lambda r:(
    {"MONITOR_PLANNED":0,"PROJECT_STAGE_REVIEW":1,"RECHECK_IN_PROGRESS":2,"RECHECK_HISTORICAL":3,"EXCLUDE":4}.get(r["priority"],5),
    r["authority"],r["project_name"]))
 review=[r for r in records if r["priority"] in ("MONITOR_PLANNED","PROJECT_STAGE_REVIEW")]
 changes=[r for r in review if r["observation"] in ("FIRST_OBSERVED","RECORD_CHANGED")]
 excluded=[r for r in records if r not in review]
 _write(root/OUTPUT,review)
 _write(root/NEW,changes)
 _write(root/EXCLUDED,excluded)
 status.update(status="REVIEW_READY" if review else
    "EVIDENCE_PRESENT_NO_ELIGIBLE_REVIEW" if records else "NO_EVIDENCE",
    total_evidence_candidates=len(records),review_records=len(review),
    new_or_changed_review=len(changes),excluded_or_deferred=len(excluded),
    verified_open_tenders=0)
 (root/STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
 return status
