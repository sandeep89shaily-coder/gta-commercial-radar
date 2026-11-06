"""Offline, source-attributed import of saved official Burlington project pages.

This deliberately makes no network requests. The browser may save publicly
accessible city project pages. A manifest preserves the exact official URL.
Not an automated source, and not proof of the original publication date.
"""
from __future__ import annotations
import csv, datetime as dt, hashlib, json, re
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

MANIFEST = "burlington_pages_manifest.csv"
STATUS = "GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_STATUS.json"
ALL = "GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_APPLICATIONS.csv"
CHANGES = "GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_NEW_OR_CHANGED.csv"
LEDGER = "GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_SEEN.json"
FIELDS = ("project_id","city","application_id","project_title","description","source_url",
          "first_seen_local","observation","changed_fields","provenance",
          "date_basis","verification_required")
FILE_NO = re.compile(r"(?<![A-Za-z0-9])(?:505|510|520|525|535)-\d{1,4}\s*[/\-]\s*\d{2}(?!\d)", re.I)
MAX_HTML_BYTES = 2_000_000
MAX_PAGES = 150

def _valid_url(url):
    try:
        p = urlparse(url)
        return (p.scheme == "https" and p.hostname in ("burlington.ca","www.burlington.ca")
                and p.path.startswith("/en/news/current-development-projects/")
                and p.path.endswith(".aspx") and not p.query and not p.fragment
                and not p.username and not p.password and p.port in (None,443))
    except ValueError:
        return False

def _parse(html, url):
    soup=BeautifulSoup(html, "html.parser")
    main=soup.find("main") or soup
    heading=main.find("h1")
    title=heading.get_text(" ",strip=True) if heading else ""
    if not title or len(title)>350:raise ValueError("MISSING_PROJECT_PAGE_TITLE")
    # Section extraction must be bounded so neighboring numbers (phone, dates,
    # addresses) cannot become invented planning file numbers.
    section=None
    for node in main.find_all(["h2","h3","h4","strong","b"]):
        if re.fullmatch(r"File Numbers?", node.get_text(" ",strip=True),re.I):
            section=node
            break
    if section is None:raise ValueError("NO_FILE_NUMBERS_SECTION")
    parts=[]
    for sibling in section.parent.next_siblings:
        if getattr(sibling,"name",None) in ("h2","h3","h4"):break
        text=sibling.get_text(" ",strip=True) if hasattr(sibling,"get_text") else str(sibling).strip()
        parts.append(text)
        if len(" ".join(parts))>1200:break
    # Some content templates place the heading and list inside a single wrapper.
    if not any(FILE_NO.search(t) for t in parts):
        wrapper=section.parent.parent
        text=wrapper.get_text(" ",strip=True)[:1500] if wrapper else ""
        marker=re.search(r"File Numbers?",text,re.I)
        if marker:parts=[text[marker.end():]]
    numbers=sorted(set(m.group(0).upper().replace(" ","") for m in FILE_NO.finditer(" ".join(parts))))
    if not numbers:raise ValueError("NO_RECOGNIZED_BURLINGTON_FILE_NUMBERS")
    description=""
    for node in main.find_all(["h2","h3","h4","strong"]):
        if "proposed development" in node.get_text(" ",strip=True).lower():
            desc=[]
            for sibling in node.parent.next_siblings:
                if getattr(sibling,"name",None) in ("h2","h3","h4"):break
                piece=sibling.get_text(" ",strip=True) if hasattr(sibling,"get_text") else str(sibling).strip()
                desc.append(piece)
                if len(" ".join(desc))>1000:break
            description=" ".join(desc)[:1000]
            break
    return [dict(project_id="OFFICIAL_PAGE:BURLINGTON:"+n,city="Burlington",
                 application_id=n,project_title=title,description=description,
                 source_url=url,provenance="USER_SAVED_OFFICIAL_WEBPAGE_UNVERIFIED_CAPTURE",
                 date_basis="NO_VERIFIED_FIRST_PUBLICATION_DATE",
                 verification_required="Independently verify city file number, webpage provenance, status and first-publication date")
            for n in numbers]

def _write(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:("'"+str(row.get(k,"")) if str(row.get(k,"")).startswith(("=","+","-","@")) else row.get(k,""))
                             for k in FIELDS})

def run(results,*,today=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    folder=root/"official_exports"/"burlington_pages"
    manifest=folder/MANIFEST
    status={"city":"Burlington","status":"MISSING_SAVED_OFFICIAL_PAGES",
            "pages_processed":0,"application_id_rows":0,"new_or_changed":0,
            "automated_source_recovered":False,"source_authenticity_verified":False,
            "errors":[]}
    allrows=[];changed=[]
    ledger_path=root/LEDGER
    previous=json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {"schema":1,"seen":{}}
    if previous.get("schema")!=1:raise ValueError("UNKNOWN_BURLINGTON_PAGE_LEDGER")
    old=previous["seen"];updated=dict(old)
    if manifest.is_file():
        with manifest.open(encoding="utf-8-sig",newline="") as fp:
            items=list(csv.DictReader(fp))
        if len(items)>MAX_PAGES:raise ValueError("TOO_MANY_BURLINGTON_SAVED_PAGES")
        if not items or any(not {"url","html_file"}.issubset(x) for x in items):
            status["status"]="INVALID_MANIFEST"
        else:
            status["status"]="ASSISTED_PAGES_PROCESSED"
            by_id={}
            for item in items:
                try:
                    url=item["url"].strip()
                    filename=item["html_file"].strip()
                    if not _valid_url(url):raise ValueError("NOT_OFFICIAL_PROJECT_URL")
                    if filename!=Path(filename).name or not filename.lower().endswith((".html",".htm")):
                        raise ValueError("UNSAFE_HTML_FILENAME")
                    file=folder/filename
                    if not file.is_file() or file.stat().st_size>MAX_HTML_BYTES:
                        raise ValueError("MISSING_OR_OVERSIZED_SAVED_PAGE")
                    rows=_parse(file.read_text(encoding="utf-8-sig"),url)
                    for row in rows:
                        if row["project_id"] in by_id and by_id[row["project_id"]]!=row:
                            raise ValueError("CONFLICTING_FILE_NUMBER:"+row["application_id"])
                        by_id[row["project_id"]]=row
                    status["pages_processed"]+=1
                except (ValueError,OSError,UnicodeError) as err:
                    status["errors"].append({"html_file":str(item.get("html_file",""))[:100],
                                             "error":type(err).__name__+":"+str(err)[:120]})
            if status["errors"]:status["status"]="PARTIAL_SAVED_PAGE_REVIEW"
            today=(today or dt.date.today()).isoformat()
            baseline=not any(k.startswith("OFFICIAL_PAGE:BURLINGTON:") for k in old)
            for pid,row in sorted(by_id.items()):
                digest=hashlib.sha256(json.dumps({k:row[k] for k in ("project_title","description","source_url")},sort_keys=True).encode()).hexdigest()
                prior=old.get(pid)
                observation="INITIAL_BASELINE" if baseline else "FIRST_OBSERVED" if prior is None else "RECORD_CHANGED" if prior["digest"]!=digest else "UNCHANGED"
                row.update(first_seen_local=prior["first_seen_local"] if prior else today,
                           observation=observation,changed_fields="OFFICIAL_PAGE_CONTENT_CHANGED_VERIFY" if observation=="RECORD_CHANGED" else "")
                allrows.append(row)
                if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):changed.append(row)
                updated[pid]={"digest":digest,"first_seen_local":row["first_seen_local"]}
            status.update(application_id_rows=len(allrows),new_or_changed=len(changed))
            # Avoid advancing ledger if any import failed; incomplete snapshots
            # are not safely comparable with later authorized exports.
            if not status["errors"] and allrows:
                temp=ledger_path.with_suffix(".tmp")
                temp.write_text(json.dumps({"schema":1,"seen":updated},indent=2),encoding="utf-8")
                temp.replace(ledger_path)
            elif not allrows:status["status"]="NO_VALID_SAVED_APPLICATION_IDS"
    _write(root/ALL,allrows);_write(root/CHANGES,changed)
    (root/STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status
