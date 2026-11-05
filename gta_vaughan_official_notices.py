"""Assisted, offline import of Vaughan's official saved Public Notices page.

No automated fetch or robots-policy bypass. Status and page publication
dates are not inferred from the browser-save date.
"""
from __future__ import annotations
import csv,datetime as dt,hashlib,json,re
from pathlib import Path
from bs4 import BeautifulSoup

INPUT="VAUGHAN_OFFICIAL_PUBLIC_NOTICES.html"
SOURCE="https://www.vaughan.ca/about-city-vaughan/departments/office-city-clerk/public-notices"
LEDGER="GTA_RADAR_VAUGHAN_OFFICIAL_NOTICES_SEEN.json"
ALL="GTA_RADAR_VAUGHAN_OFFICIAL_NOTICES_APPLICATIONS.csv"
NEW="GTA_RADAR_VAUGHAN_OFFICIAL_NOTICES_NEW_OR_CHANGED.csv"
STATUS="GTA_RADAR_VAUGHAN_OFFICIAL_NOTICES_STATUS.json"
FIELDS=("project_id","city","application_id","address","description","meeting_date_raw",
        "source_url","observation","first_seen_local","date_basis","provenance",
        "verification_required")
ID=re.compile(r"(?<![A-Za-z0-9])(?:OP|Z|DA|19T|A|B)\.?[- ]?\d{2,4}[./-]\d{2,4}(?![A-Za-z0-9])",re.I)
FIELD=re.compile(r"City File No\.?\s*:\s*(.*?)\s*Subject Land\s*:\s*(.*?)\s*Meeting Date\s*:\s*(.*?)\s*Meeting Type\s*:\s*(.*?)\s*Notice Description\s*:\s*(.*?)(?=\s*(?:City File No\.?\s*:|$))",re.I|re.S)

def parse(html):
    soup=BeautifulSoup(html,"html.parser")
    main=soup.find("main") or soup
    # Treat only explicitly labelled city file numbers as records.
    # Never mine arbitrary IDs from proposal narrative, footer or links.
    text=main.get_text(" ",strip=True)
    records={}
    for m in FIELD.finditer(text):
        file_field,address,meeting,meeting_type,description=(" ".join(x.split()) for x in m.groups())
        for match in ID.finditer(file_field):
            ident=match.group().upper().replace(" ","")
            pid="OFFICIAL_NOTICE:VAUGHAN:"+ident
            row={"project_id":pid,"city":"Vaughan","application_id":ident,
                 "address":address[:300],"description":description[:1200],
                 "meeting_date_raw":meeting[:50],"source_url":SOURCE,
                 "date_basis":"MEETING_DATE_NOT_ORIGINAL_PUBLICATION_DATE",
                 "provenance":"USER_SAVED_OFFICIAL_VAUGHAN_NOTICE_PAGE_NOT_AUTHENTICATED",
                 "verification_required":"Confirm public notice and municipal file in PLANit; verify current approval stage and original posting"}
            if pid in records and records[pid]!=row:
                raise ValueError("CONFLICTING_VAUGHAN_NOTICE_ID:"+ident)
            records[pid]=row
    return list(records.values())

def run(results,*,today=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    source=root/"official_exports"/INPUT
    summary={"city":"Vaughan","status":"MISSING_SAVED_PUBLIC_NOTICES",
             "application_id_rows":0,"new_or_changed":0,"automated_source_recovered":False,
             "source_authenticity_verified":False}
    allrows=[];changes=[]
    state_path=root/LEDGER
    state=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"schema":1,"seen":{}}
    if state.get("schema")!=1:raise ValueError("UNKNOWN_VAUGHAN_NOTICE_LEDGER")
    if source.is_file():
        try:
            if source.stat().st_size>3_000_000:raise ValueError("OVERSIZED_PUBLIC_NOTICE_HTML")
            parsed=parse(source.read_text(encoding="utf-8-sig"))
            if not parsed:raise ValueError("NO_CITY_FILE_NUMBER_NOTICE_RECORDS")
            old=state["seen"];seen=dict(old)
            baseline=not any(k.startswith("OFFICIAL_NOTICE:VAUGHAN:") for k in old)
            day=(today or dt.date.today()).isoformat()
            for row in sorted(parsed,key=lambda x:x["project_id"]):
                pid=row["project_id"]
                digest=hashlib.sha256(json.dumps({k:row[k] for k in ("address","description","meeting_date_raw")},sort_keys=True).encode()).hexdigest()
                previous=old.get(pid)
                obs="INITIAL_BASELINE" if baseline else "FIRST_OBSERVED" if not previous else "RECORD_CHANGED" if previous["digest"]!=digest else "UNCHANGED"
                row.update(observation=obs,first_seen_local=previous["first_seen_local"] if previous else day)
                allrows.append(row)
                if obs in ("FIRST_OBSERVED","RECORD_CHANGED"):changes.append(row)
                seen[pid]={"digest":digest,"first_seen_local":row["first_seen_local"]}
            temp=state_path.with_suffix(".tmp")
            temp.write_text(json.dumps({"schema":1,"seen":seen},indent=2),encoding="utf-8")
            temp.replace(state_path)
            summary.update(status="ASSISTED_OFFICIAL_NOTICE_BASELINED" if baseline else "ASSISTED_OFFICIAL_NOTICE_COLLECTED",
                           application_id_rows=len(allrows),new_or_changed=len(changes))
        except (ValueError,OSError,UnicodeError) as error:
            summary.update(status="REJECTED",error=type(error).__name__+":"+str(error)[:160])
    for filename,rows in ((ALL,allrows),(NEW,changes)):
        with (root/filename).open("w",encoding="utf-8-sig",newline="") as fp:
            writer=csv.DictWriter(fp,fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k:("'"+str(row.get(k,"")) if str(row.get(k,"")).startswith(("=","+","-","@")) else row.get(k,""))
                                 for k in FIELDS})
    (root/STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
