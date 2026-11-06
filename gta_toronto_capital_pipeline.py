"""Source-backed Toronto upcoming-capital procurement pipeline (not open tenders).

Parses the city's official linked PDF table, preserving scope, type, owner,
target sourcing year, indicative budget band and source URL. Uses existing
policy-aware official HTML and PDF fetchers. A first run is historical baseline.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin,urlparse

from bs4 import BeautifulSoup
from gta_regional_early_intelligence import _fetch,_safe_url,SOURCES
from gta_regional_document_evidence import _fetch_pdf

INDEX=SOURCES["Toronto"]["url"]
ALL="GTA_RADAR_TORONTO_CAPITAL_PIPELINE.csv"
CHANGES="GTA_RADAR_TORONTO_CAPITAL_NEW_OR_CHANGED.csv"
STATUS="GTA_RADAR_TORONTO_CAPITAL_PIPELINE_STATUS.json"
LEDGER="GTA_RADAR_TORONTO_CAPITAL_PIPELINE_SEEN.json"
MAX_PAGES=25
MAX_ROWS=300
FIELD_NAMES=(
 "project_id","city","project_name_contract","work_type","scope_of_work",
 "delivery_division","project_owner_division","target_sourcing_year",
 "target_award_year","sourcing_type","estimated_range",
 "estimated_contract_term_months","source_document_url","source_index_url",
 "pdf_page","pdf_row_number","source_publication_date","source_date_basis",
 "procurement_status","first_seen_local","observation","verification_required",
)

def _clean(value):
 return re.sub(r"\s+"," ",str(value or "")).strip()

def _pdf_link(html,index=INDEX):
 soup=BeautifulSoup(html,"html.parser")
 main=soup.find("main") or soup
 for a in main.find_all("a",href=True):
  link=urljoin(index,str(a["href"]).strip())
  label=_clean(a.get_text(" ",strip=True))
  if not urlparse(link).path.lower().endswith(".pdf") or not _safe_url(link,index):
   continue
  if re.search(r"capital projects|planned for procurement|upcoming.capital",label+" "+urlparse(link).path,re.I):
   return link
 return ""

def _normalise_table(row):
 if not isinstance(row,(list,tuple)) or len(row)!=11:
  return None
 v=[_clean(x) for x in row]
 if not v[0].isdigit() or not 1<=int(v[0])<=MAX_ROWS:
  return None
 name,kind,scope,delivery,owner,source_year,award_year,bid_type,band,months=v[1:]
 if len(name)<12 or len(scope)<15 or not (kind and owner):
  return None
 if not re.fullmatch(r"20\d{2}",source_year) or not re.fullmatch(r"20\d{2}",award_year):
  return None
 if months and not re.fullmatch(r"\d{1,3}",months):
  return None
 return dict(pdf_row_number=int(v[0]),project_name_contract=name[:300],
   work_type=kind[:80],scope_of_work=scope[:2500],
   delivery_division=delivery[:180],project_owner_division=owner[:180],
   target_sourcing_year=source_year,target_award_year=award_year,
   sourcing_type=bid_type[:120],estimated_range=band[:80],
   estimated_contract_term_months=months)

def _parse_pdf(content,*,parser=None):
 if not isinstance(content,(bytes,bytearray)) or len(content)>4_500_000 or not content.startswith(b"%PDF-"):
  raise ValueError("NOT_BOUNDED_OFFICIAL_CAPITAL_PDF")
 if parser is None:
  import pdfplumber
  parser=pdfplumber.open
 rows=[];rejected=0
 with parser(io.BytesIO(content)) as doc:
  if len(doc.pages)==0 or len(doc.pages)>MAX_PAGES:
   raise ValueError("CAPITAL_PDF_PAGE_LIMIT")
  for page_no,page in enumerate(doc.pages,1):
   tables=page.extract_tables(table_settings={
      "vertical_strategy":"lines","horizontal_strategy":"lines",
      "snap_tolerance":3,"join_tolerance":3,
   }) or []
   for table in tables:
    for item in table:
     row=_normalise_table(item)
     if row:
      row["pdf_page"]=page_no
      rows.append(row)
     elif item and len(item)==11 and re.fullmatch(r"\d+",_clean(item[0])):
      rejected+=1
 if len(rows)>MAX_ROWS:
  raise ValueError("CAPITAL_PDF_ROW_LIMIT")
 numbers=[r["pdf_row_number"] for r in rows]
 if len(numbers)!=len(set(numbers)):
  raise ValueError("DUPLICATE_OFFICIAL_CAPITAL_PROJECT_ROW")
 return sorted(rows,key=lambda x:x["pdf_row_number"]),rejected

def _write(path,rows):
 with path.open("w",encoding="utf-8-sig",newline="") as fp:
  writer=csv.DictWriter(fp,fieldnames=FIELD_NAMES,extrasaction="ignore")
  writer.writeheader()
  for row in rows:
   writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v)
                    for k,v in row.items() if k in FIELD_NAMES})

def run(results,*,today=None,html_fetcher=None,pdf_fetcher=None,pdf_parser=None,
        min_complete_rows=10):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 day=(today or dt.date.today()).isoformat()
 ledger=root/LEDGER
 prior=json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"schema":1,"seen":{}}
 if prior.get("schema")!=1 or not isinstance(prior.get("seen"),dict):
  raise ValueError("UNSUPPORTED_CAPITAL_PDF_LEDGER")
 old=prior["seen"];updated=dict(old);output=[];changes=[]
 state={"status":"FAILED","source_index_url":INDEX,
   "official_pdf_url":"","parsed_projects":0,"rejected_table_rows":0,
   "new_or_changed":0,"verified_open_tenders":0,"paid_ai_calls":0,
   "warning":"These are preliminary planned source/award years and value ranges, not confirmed open tenders or actual dates."}
 try:
  pdf_url=_pdf_link((html_fetcher or _fetch)(INDEX))
  if not pdf_url:
   raise ValueError("NO_SAME_HOST_CAPITAL_PIPELINE_PDF_LINK")
  state["official_pdf_url"]=pdf_url
  data=(pdf_fetcher or _fetch_pdf)(pdf_url)
  parsed,rejected=_parse_pdf(data,parser=pdf_parser)
  state.update(parsed_projects=len(parsed),rejected_table_rows=rejected)
  if len(parsed)<min_complete_rows or rejected:
   state["status"]="INCOMPLETE_OFFICIAL_PDF_PARSE"
  else:
   baseline=not any(k.startswith("TORONTO_CAPITAL:") for k in old)
   for record in parsed:
    canonical=_clean(record["project_name_contract"]).casefold()
    pid="TORONTO_CAPITAL:"+hashlib.sha256(canonical.encode()).hexdigest()[:24]
    record.update(project_id=pid,city="Toronto",
      source_document_url=pdf_url,source_index_url=INDEX,
      source_publication_date="",
      source_date_basis="OFFICIAL_CAPITAL_PDF_TARGET_YEARS_NOT_FIRST_PUBLICATION",
      procurement_status="PLANNED_PIPELINE_NOT_VERIFIED_OPEN_TENDER",
      verification_required="Check Toronto bids portal for solicitation, award, purchaser and current procurement stage")
    digest=hashlib.sha256(json.dumps({k:record[k] for k in
      ("work_type","scope_of_work","delivery_division","project_owner_division",
       "target_sourcing_year","target_award_year","sourcing_type","estimated_range",
       "estimated_contract_term_months")},sort_keys=True).encode()).hexdigest()
    previous=old.get(pid)
    observation=("INITIAL_BASELINE" if baseline else "FIRST_OBSERVED" if previous is None
                 else "RECORD_CHANGED" if previous["digest"]!=digest else "UNCHANGED")
    record.update(first_seen_local=previous["first_seen_local"] if previous else day,
                  observation=observation)
    output.append(record)
    if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):
     changes.append(record)
    updated[pid]={"first_seen_local":record["first_seen_local"],"digest":digest}
   state.update(status="BASELINE_COMPLETE" if baseline else "COLLECTED",
                new_or_changed=len(changes))
 except Exception as error:
  state["error"]=type(error).__name__+":"+str(error)[:200]
 _write(root/ALL,output);_write(root/CHANGES,changes)
 if state["status"] in ("BASELINE_COMPLETE","COLLECTED") and updated!=old:
  tmp=ledger.with_suffix(".tmp")
  tmp.write_text(json.dumps({"schema":1,"seen":updated},indent=2),encoding="utf-8")
  tmp.replace(ledger)
 (root/STATUS).write_text(json.dumps(state,indent=2),encoding="utf-8")
 return state
