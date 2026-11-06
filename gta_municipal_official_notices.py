"""Permitted official-page application-number recovery (Burlington and Vaughan).

Never counts an index fetch or a saved manual export as automatic coverage.
No bypass of robots, redirects or access denial: uses the shared, bounded,
policy-aware official HTML client. Kitchener/blocked York cities remain in
an explicit separate recovery status, not silently marked covered.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from gta_regional_early_intelligence import _fetch, _safe_url

BURLINGTON="https://www.burlington.ca/en/planning-and-development/planning-and-development.aspx"
BURLINGTON_PROJECT_PREFIX="https://www.burlington.ca/en/news/current-development-projects/"
VAUGHAN="https://www.vaughan.ca/about-city-vaughan/departments/office-city-clerk/public-notices"
SOURCES={"Burlington":BURLINGTON,"Vaughan":VAUGHAN}
OUTPUT="GTA_RADAR_MUNICIPAL_OFFICIAL_APPLICATIONS.csv"
CHANGES="GTA_RADAR_MUNICIPAL_OFFICIAL_APPLICATIONS_NEW_OR_CHANGED.csv"
STATUS="GTA_RADAR_MUNICIPAL_OFFICIAL_APPLICATIONS_STATUS.json"
LEDGER="GTA_RADAR_MUNICIPAL_OFFICIAL_APPLICATIONS_SEEN.json"
FIELDS=("project_id","city","application_id","project_title","address",
        "scope_of_work","current_status","owner_or_applicant","contact_evidence",
        "source_url","official_index_url","source_publication_date",
        "source_date_basis","first_seen_local","observation",
        "verification_required")
MAX_BURLINGTON_PAGES=45
MAX_ROWS=175
BURLINGTON_ID=re.compile(r"(?<!\w)(?:505|510|520|525|535)-\d{1,4}\s*/\s*\d{2}(?!\d)",re.I)
VAUGHAN_ID=re.compile(r"(?<![A-Za-z0-9])(?:OP|Z|DA|19T)\.\d{2}\.\d{3}(?!\d)",re.I)
LABEL=re.compile(r"\b(?:City\s+)?File\s+No\.?\s*:\s*",re.I)
STATUS_RE=re.compile(r"\bStatus\s*[-:]\s*(Under Review|Approved|Appealed|On Hold|Refused|Pre-Application|Closed|Complete)\b",re.I)
SCOPE=re.compile(r"(?:Proposed Development|Notice Description|Description of Development)",re.I)
CLOSED=re.compile(r"\b(?:closed|refused|withdrawn|cancelled|completed)\b",re.I)
def _clean(x): return re.sub(r"\s+"," ",str(x or "")).strip()

def _burlington_links(html):
    soup=BeautifulSoup(html,"html.parser")
    main=soup.find("main") or soup
    result=[];seen=set()
    for a in main.find_all("a",href=True):
        url=urljoin(BURLINGTON,str(a["href"]).strip())
        path=urlparse(url).path.lower()
        if not (_safe_url(url,BURLINGTON) and
                path.startswith("/en/news/current-development-projects/") and
                path.endswith(".aspx") and not urlparse(url).query and url!=BURLINGTON):
            continue
        if url in seen: continue
        seen.add(url);result.append(url)
        if len(result)>=MAX_BURLINGTON_PAGES: break
    return result

def _burlington_rows(html,url):
    soup=BeautifulSoup(html,"html.parser")
    main=soup.find("main")
    if main is None: return []
    title_node=main.find("h1")
    title=_clean(title_node.get_text(" ",strip=True)) if title_node else ""
    if not title: return []
    text=_clean(main.get_text(" ",strip=True))
    match=re.search(r"\bFile Numbers?\b",text,re.I)
    if not match:return []
    # Only scan the labelled file-number section, never the whole page.
    bounded=text[match.end():match.end()+200]
    ids=list(dict.fromkeys(m.group().replace(" ","").upper() for m in BURLINGTON_ID.finditer(bounded)))
    if not ids:return []
    status=""
    m=STATUS_RE.search(text[:350])
    if m:status=m.group(1)[:70]
    address=""
    m=re.search(r"\bSite Address\s+(.{4,160}?)(?=\s+(?:Public Engagement|Applicant|Proposed Development|Development Rendering|Site Plan Rendering)\b|$)",text,re.I)
    if m:address=_clean(m.group(1))[:160]
    scope=""
    m=re.search(r"\bProposed Development\s+(.{30,1400}?)(?=\s+(?:Learn more|Planner on File|Planners on File|File Numbers?|Public Meetings)\b|$)",text,re.I)
    if m:scope=_clean(m.group(1))[:1000]
    applicant=""
    m=re.search(r"\bApplicant\s+(.{4,240}?)(?=\s+(?:Proposed Development|Planner on File|Planners on File)\b|$)",text,re.I)
    if m:applicant=_clean(m.group(1))[:200]
    return [_row("Burlington",ident,title,address,scope,status,applicant,url)
            for ident in ids]

def _row(city,ident,title,address,scope,status,applicant,url):
    identity=city.upper().replace(" ","_")+"|"+ident
    return {"project_id":"OFFICIAL_NOTICE:"+hashlib.sha256(identity.encode()).hexdigest()[:24],
        "city":city,"application_id":ident,"project_title":title[:240],
        "address":address[:200],"scope_of_work":scope[:1100],
        "current_status":status[:120],"owner_or_applicant":applicant[:200],
        "contact_evidence":"",
        "source_url":url,"official_index_url":SOURCES[city],
        "source_publication_date":"","source_date_basis":"NO_VERIFIED_FIRST_PUBLICATION",
        "verification_required":"Verify city file number, actual publication date, applicant, stage, contract awards and buyer"}

def _vaughan_rows(html):
    """Structured public notices only; headings and bounded text are evidence."""
    soup=BeautifulSoup(html,"html.parser")
    main=soup.find("main") or soup.find("article")
    if main is None:return []
    for tag in main.select("nav,footer,script,style,form"):tag.decompose()
    text=_clean(main.get_text(" ",strip=True))
    rows=[]
    for match in LABEL.finditer(text):
        # Each notice's city file number precedes subject-land and description.
        number_section=text[match.end():match.end()+100]
        ids=list(dict.fromkeys(m.group().upper() for m in VAUGHAN_ID.finditer(number_section)))
        if not ids:continue
        following=text[match.end():match.end()+900]
        addr=""
        address_match=re.search(r"\bSubject Land\s*:\s*(.{5,170}?)(?=\s+(?:Meeting Date|Meeting Type|Notice Description|Notice Type|City File No\.?)\b|$)",following,re.I)
        if address_match:addr=_clean(address_match.group(1))[:170]
        scope=""
        scope_match=re.search(r"\bNotice Description\s*:\s*(.{30,550}?)(?=\s+(?:Notice Type|City File No\.?|Minor Variance Application|Public Notification Registry)\b|$)",following,re.I)
        if scope_match:scope=_clean(scope_match.group(1))[:550]
        before=text[max(0,match.start()-140):match.start()]
        title_match=re.search(r"Notice Type\s*:\s*(.{5,120})$",before,re.I)
        title=_clean(title_match.group(1)) if title_match else "Vaughan planning notice"
        for ident in ids[:5]:
            rows.append(_row("Vaughan",ident,title,addr,scope,"PUBLIC_NOTICE", "",VAUGHAN))
        if len(rows)>=MAX_ROWS:break
    return list({row["project_id"]:row for row in rows}.values())

def _write(path,records):
    with path.open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS,extrasaction="ignore");writer.writeheader()
        for row in records:
            writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@"))
                               else v) for k,v in row.items() if k in FIELDS})

def run(results,*,today=None,fetcher=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    path=root/LEDGER
    prior=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema":1,"seen":{}}
    if prior.get("schema")!=1 or not isinstance(prior.get("seen"),dict):
        raise ValueError("INVALID_MUNICIPAL_OFFICIAL_NOTICE_LEDGER")
    old=prior["seen"];updated=dict(old);records=[];changes=[];status=[]
    loader=fetcher or _fetch
    for city,url in SOURCES.items():
        audit={"city":city,"index_url":url,"status":"FAILED",
               "application_id_rows":0,"notice_pages_attempted":0,
               "notice_pages_fetched":0,"new_or_changed":0,
               "citywide_complete":False,"first_publication_verified":False}
        try:
            html=loader(url)
            if city=="Burlington":
                # City planning hub points to an official current-projects
                # index. Inspect at most one same-host index then bounded
                # official detail pages. Never fetch unrelated domains.
                links=_burlington_links(html)
                if not links:
                    soup=BeautifulSoup(html,"html.parser")
                    for a in soup.find_all("a",href=True):
                        label=_clean(a.get_text(" ",strip=True))
                        target=urljoin(url,str(a["href"]).strip())
                        if ("Current Development Projects" in label and
                            _safe_url(target,url) and not urlparse(target).query):
                            links=_burlington_links(loader(target))
                            audit["project_index_url"]=target
                            break
                audit["notice_pages_attempted"]=len(links)
                found=[]
                for link in links:
                    try:
                        found.extend(_burlington_rows(loader(link),link))
                        audit["notice_pages_fetched"]+=1
                    except Exception as exc:
                        audit.setdefault("page_errors",[]).append({
                            "url":link,"error":type(exc).__name__+":"+str(exc)[:150]})
            else:
                found=_vaughan_rows(html)
            if len(found)>MAX_ROWS:raise ValueError("OFFICIAL_NOTICE_ROW_LIMIT")
            unique={r["project_id"]:r for r in found}
            baseline=not any(key.startswith("OFFICIAL_NOTICE:") and
                             val.get("city")==city for key,val in old.items())
            for row in sorted(unique.values(),key=lambda r:r["project_id"]):
                key=row["project_id"]
                digest=hashlib.sha256(json.dumps({k:row[k] for k in
                   ("project_title","address","scope_of_work","current_status","owner_or_applicant")},
                   sort_keys=True).encode()).hexdigest()
                previous=old.get(key)
                observation=("INITIAL_BASELINE" if baseline else
                    "FIRST_OBSERVED" if previous is None else
                    "RECORD_CHANGED" if previous["digest"]!=digest else "UNCHANGED")
                row.update(first_seen_local=previous["first_seen_local"] if previous else day,
                           observation=observation)
                records.append(row)
                if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):changes.append(row)
                updated[key]={"digest":digest,"first_seen_local":row["first_seen_local"],"city":city}
            audit["application_id_rows"]=len(unique)
            audit["new_or_changed"]=sum(x["city"]==city for x in changes)
            audit["status"]=("BASELINE_COMPLETE" if baseline else "COLLECTED") if unique else "NO_APPLICATION_IDS_EXTRACTED"
        except Exception as exc:
            audit["error"]=type(exc).__name__+":"+str(exc)[:170]
        status.append(audit)
    _write(root/OUTPUT,records);_write(root/CHANGES,changes)
    if updated!=old:
        temp=path.with_suffix(".tmp")
        temp.write_text(json.dumps({"schema":1,"seen":updated},indent=2),encoding="utf-8")
        temp.replace(path)
    result={"cities_configured":2,"cities_with_application_ids":sum(x["application_id_rows"]>0 for x in status),
      "application_id_rows":len(records),"new_or_changed":len(changes),
      "cities_verified_citywide_complete":0,"source_status":status,
      "warning":"Strict official file numbers only. Current status, original publication and citywide coverage are unverified. HTTP restrictions are not bypassed; manual exports remain separate."}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
