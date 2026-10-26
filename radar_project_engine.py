"""Evidence-first project indexing for existing V8/early records and local public documents.

No network calls, AI, invented buyers, or claims of unawarded contracts.
Source records are preserved in radar_master.sqlite; this is a derived index.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import radar_workspace as workspace

PROJECT_FILE = "GTA_RADAR_PROJECT_RESEARCH.csv"
REVIEW_FILE = "GTA_RADAR_PROJECT_REVIEW.csv"
LINK_FILE = "GTA_RADAR_PROJECT_LINKS_REVIEW.csv"
DOCUMENT_FILE = "GTA_RADAR_DOCUMENT_REVIEW.csv"
SCOPE = re.compile(
    r"\b(?:industr(?:y|ial)|manufactur\w*|factor(?:y|ies)|warehouse|"
    r"distribution cent(?:er|re)|logistics|retail|commercial|office|"
    r"hotel|restaurant|grocery|supermarket|medical clinic|data cent(?:er|re)|"
    r"cold storage|refrigerat\w*|processing plant|industrial addition|"
    r"self.storage|car wash|laborator\w*|business expansion|"
    r"new (?:store|facility|plant)|equipment installation)\b", re.I)
INACTIVE = re.compile(r"\b(?:withdrawn|cancelled|canceled|refused|rejected|abandoned)\b", re.I)
SUITABLE = re.compile(
    r"(?:planning|rezon|site.plan|preconsult|develop|building.permit|"
    r"industrial|investment|capex|commercial|construction|proposals|"
    r"tender|business.opening|facility|manufactur)", re.I)
STREET = re.compile(r"^\s*([1-9][0-9]{0,5}[A-Z]?)\s+(.+?)\s*$", re.I)
ROAD = re.compile(r"\b(?:ST(?:REET)?|RD|ROAD|AVE(?:NUE)?|DR(?:IVE)?|"
                  r"BLVD|BOULEVARD|CRES(?:CENT)?|CT|COURT|WAY|LANE|"
                  r"PKWY|PARKWAY)\b", re.I)
FIELDS = ("project_id","city","address","application_id","description",
          "stage","first_observed_at","source_date","date_basis",
          "source_count","source_url","review_state","review_reason",
          "buyer_status","supplier_selection_status")
LINK_FIELDS = ("left_project_id","right_project_id","address","city",
               "status","reason")
DOCUMENT_FIELDS = ("document_id","filename","document_type","status",
                   "extracted_chars","source_url","reason")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def norm(value):
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", str(value or "").upper()).split())


def address_key(city, address):
    # Refuse fuzzy addresses, lots, intersections and regional-only locations.
    m = STREET.match(str(address or "").strip())
    if not m or not norm(city) or norm(city) in ("YORK REGION", "ONTARIO"):
        return ""
    street = norm(m.group(2))
    if not ROAD.search(street):
        return ""
    abbreviations = {"STREET":"ST","ROAD":"RD","AVENUE":"AVE","DRIVE":"DR",
                     "BOULEVARD":"BLVD","CRESCENT":"CRES","COURT":"CT",
                     "PARKWAY":"PKWY","NORTH":"N","SOUTH":"S","EAST":"E","WEST":"W"}
    words = [abbreviations.get(w,w) for w in street.split()]
    # Keep unit numbers / suffixes: they can distinguish different tenants.
    return norm(city) + "|" + norm(m.group(1)) + " " + " ".join(words)


def valid_url(value):
    u = urlparse(str(value or "").strip())
    return str(value).strip() if u.scheme == "https" and u.hostname and not u.username and not u.password else ""


def pick(data, *keys):
    for key in keys:
        v=data.get(key)
        if isinstance(v,(str,int,float)) and str(v).strip():
            return str(v).strip()
    return ""


def setup(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS project_nodes(
       project_id TEXT PRIMARY KEY, identity_key TEXT NOT NULL,
       city TEXT, address TEXT, application_id TEXT, description TEXT,
       stage TEXT, first_observed_at TEXT, source_date TEXT,
       date_basis TEXT, source_url TEXT, scope_evidence INTEGER NOT NULL,
       source_count INTEGER NOT NULL, review_state TEXT NOT NULL,
       review_reason TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS project_record_edges(
       project_id TEXT NOT NULL, source_id TEXT NOT NULL, record_id TEXT NOT NULL,
       PRIMARY KEY(project_id,source_id,record_id)
    );
    CREATE INDEX IF NOT EXISTS ix_project_records ON project_record_edges(source_id,record_id);
    CREATE TABLE IF NOT EXISTS project_facts(
       fact_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, field_name TEXT NOT NULL,
       field_value TEXT NOT NULL, source_id TEXT, record_id TEXT, document_id TEXT,
       source_url TEXT, locator TEXT, verification TEXT NOT NULL,
       observed_at TEXT, date_basis TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_project_facts_project ON project_facts(project_id,document_id);
    CREATE TABLE IF NOT EXISTS project_documents(
       document_id TEXT PRIMARY KEY, filename TEXT NOT NULL,
       source_url TEXT, document_type TEXT, public_date TEXT, city TEXT,
       address TEXT, application_id TEXT, sha256 TEXT, extracted_text TEXT,
       extraction_status TEXT NOT NULL, reason TEXT, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS project_review_links(
       left_project_id TEXT NOT NULL, right_project_id TEXT NOT NULL,
       address TEXT, city TEXT, status TEXT NOT NULL, reason TEXT NOT NULL,
       PRIMARY KEY(left_project_id,right_project_id)
    );
    """)


def project_identity(city, app, sid, rid):
    citykey=norm(city)
    appkey=norm(app)
    # A municipal application number is a strong identity only with jurisdiction.
    if appkey and citykey and appkey not in ("0","NONE","UNKNOWN","N A"):
        identity="APPLICATION|"+citykey+"|"+appkey
    else:
        identity="SOURCE_RECORD|"+str(sid)+"|"+str(rid)
    return "PRJ-"+digest(identity)[:20],identity


def add_fact(db, pid, field, value, *, sid="",rid="",doc="",url="",
             locator="", verification="PUBLIC_RECORD_FIELD", observed="", date_basis=""):
    value=str(value or "").strip()[:1500]
    if not value:
        return
    evidence="|".join((pid,field,value,sid,rid,doc,locator))
    db.execute("""INSERT OR IGNORE INTO project_facts
        (fact_id,project_id,field_name,field_value,source_id,record_id,
         document_id,source_url,locator,verification,observed_at,date_basis)
         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (digest(evidence),pid,field,value,sid,rid,doc,url,locator,
         verification,observed,date_basis))


def read_documents(db, home, now):
    directory=Path(home)/"Data"/"official_documents"
    manifest=directory/"manifest.csv"
    if not manifest.is_file():
        return 0
    from bs4 import BeautifulSoup
    from pypdf import PdfReader
    count=0
    with manifest.open(encoding="utf-8-sig",newline="") as handle:
        for row in csv.DictReader(handle):
            name=str(row.get("filename") or "").strip()
            url=valid_url(row.get("source_url"))
            doc_type=str(row.get("document_type") or "OFFICIAL_DOCUMENT")[:100]
            public_date=str(row.get("public_date") or "").strip()[:10]
            city=str(row.get("city") or "").strip()[:120]
            address=str(row.get("address") or "").strip()[:240]
            app=str(row.get("application_id") or "").strip()[:100]
            filename=Path(name)
            # A manifest is not trusted as arbitrary filesystem access.
            if not name or filename.name != name or filename.suffix.lower() not in (".pdf",".txt",".html",".htm"):
                continue
            path=directory/filename.name
            if path.is_symlink() or path.resolve().parent != directory.resolve():
                continue
            doc_id="DOC-"+digest(name+"|"+url)[:20]
            status="READY"; reason=""; text=""
            raw=b""; sha=""
            try:
                if not path.is_file() or path.stat().st_size > 12_000_000:
                    raise ValueError("missing document or exceeds 12 MB")
                raw=path.read_bytes()
                sha=hashlib.sha256(raw).hexdigest()
                if filename.suffix.lower()==".pdf":
                    reader=PdfReader(str(path))
                    pages=[]
                    for i,page in enumerate(reader.pages[:40]):
                        body=(page.extract_text() or "").strip()
                        if body:
                            pages.append("[page "+str(i+1)+"] "+body)
                    text="\n".join(pages)
                else:
                    plain=raw.decode("utf-8-sig")
                    text=BeautifulSoup(plain,"html.parser").get_text(" ",strip=True) if filename.suffix.lower() in (".html",".htm") else plain
                text=text[:30000]
                if len(text.strip())<40:
                    status="REVIEW";reason="NO_READABLE_TEXT_OR_SCANNED_PDF"
                if not url:
                    status="REVIEW";reason="SOURCE_URL_MISSING_OR_NOT_HTTPS"
            except Exception as exc:
                # Store the failure, never turn it into a successful project.
                status="ERROR";reason=type(exc).__name__+": "+str(exc)[:120]
            db.execute("""INSERT INTO project_documents
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(document_id) DO UPDATE SET
               filename=excluded.filename,source_url=excluded.source_url,
               document_type=excluded.document_type,public_date=excluded.public_date,
               city=excluded.city,address=excluded.address,application_id=excluded.application_id,
               sha256=excluded.sha256,extracted_text=excluded.extracted_text,
               extraction_status=excluded.extraction_status,reason=excluded.reason,
               updated_at=excluded.updated_at""",
               (doc_id,name,url,doc_type,public_date,city,address,app,sha,text,status,reason,now))
            count+=1
            if status=="READY" and city and (app or address_key(city,address)) and SCOPE.search(text):
                pid,identity=project_identity(city,app,"official_document",doc_id)
                if not app:
                    pid,identity=project_identity("","","official_document",doc_id)
                snippet=SCOPE.search(text)
                before=max(0,snippet.start()-120)
                after=min(len(text),snippet.end()+180)
                quote=" ".join(text[before:after].split())[:350]
                existing=db.execute("SELECT source_count FROM project_nodes WHERE project_id=?",
                                    (pid,)).fetchone()
                db.execute("""INSERT INTO project_nodes
                (project_id,identity_key,city,address,application_id,description,stage,
                 first_observed_at,source_date,date_basis,source_url,scope_evidence,
                 source_count,review_state,review_reason,updated_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(project_id) DO UPDATE SET
                 scope_evidence=1,source_url=excluded.source_url,updated_at=excluded.updated_at""",
                 (pid,identity,city,address,app,quote,doc_type,now,public_date,
                  "MANIFEST_DATE_UNVERIFIED_AS_PUBLIC_POSTING",url,1,
                  existing[0] if existing else 1,"REVIEW_REQUIRED","DOCUMENT_ONLY_NEEDS_IDENTITY_REVIEW",now))
                page_markers=re.findall(r"\\[page (\\d+)\\]",text[:snippet.start()])
                locator=("PDF page "+page_markers[-1]) if page_markers else "document text"
                add_fact(db,pid,"document_scope_excerpt",quote,doc=doc_id,url=url,
                         locator=locator,verification="DOCUMENT_TEXT_EXTRACTION_NOT_FACT_CHECKED",
                         observed=now,date_basis="MANIFEST_DATE_UNVERIFIED")
    return count


def ingest_records(db, now):
    # Derived index rebuilt transactionally so stale links/facts do not persist.
    # Restrict high-volume registries (e.g. childcare, DineSafe, licences).
    rows=db.execute("SELECT source_id,record_id,first_seen_at,source_date,payload_json "
                    "FROM records ORDER BY source_id,record_id")
    accepted=0
    for sid,rid,first,date,payload in rows:
        if not SUITABLE.search(sid):
            continue
        try:
            info=json.loads(payload)
            if not isinstance(info,dict):
                continue
        except (TypeError,ValueError):
            continue
        if info.get("_radar_v8_active") is False:
            continue
        city=pick(info,"city","municipality","MUN_NAME","jurisdiction")
        app=pick(info,"application_id","municipal_reference","application_number",
                 "APP_NUMBER","file_number")
        address=pick(info,"location","site","address","site_address","SITE_ADDRESS")
        description=pick(info,"description","title","project_description","name")
        stage=pick(info,"stage","status","application_status")
        url=valid_url(pick(info,"exact_source_record_url","source_url","official_page"))
        scope=bool(SCOPE.search(description) or
                   info.get("commercial_signal") in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"))
        if not scope:
            continue
        pid,identity=project_identity(city,app,sid,rid)
        date_basis=pick(info,"source_date_basis","date_basis") or "SOURCE_DATE_NOT_PROVEN_POSTING"
        source_date=pick(info,"source_application_date","source_date") or date or ""
        db.execute("""INSERT OR IGNORE INTO project_nodes
          (project_id,identity_key,city,address,application_id,description,stage,
           first_observed_at,source_date,date_basis,source_url,scope_evidence,
           source_count,review_state,review_reason,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (pid,identity,city,address,app,description[:550],stage,
           first or "",source_date,date_basis,url,1,0,"REVIEW_REQUIRED","NOT_GATED",now))
        db.execute("INSERT OR IGNORE INTO project_record_edges VALUES(?,?,?)",(pid,sid,rid))
        for field,value in (("municipality",city),("application_id",app),
                            ("address",address),("description",description),
                            ("stage",stage),("source_date",source_date)):
            add_fact(db,pid,field,value,sid=sid,rid=rid,url=url,
                     locator="source record "+rid,observed=first or "",
                     date_basis=date_basis)
        accepted+=1
    return accepted


def finalize(db, now):
    # Source record edges define the actual membership; address is review-only.
    nodes=list(db.execute(
        "SELECT project_id,city,address,application_id,description,stage,source_url,"
        "first_observed_at FROM project_nodes"))
    by_address=defaultdict(list)
    for pid,city,address,app,description,stage,url,first in nodes:
        n=db.execute("SELECT COUNT(*) FROM project_record_edges WHERE project_id=?",
                     (pid,)).fetchone()[0]
        doc=db.execute("SELECT COUNT(*) FROM project_facts WHERE project_id=? AND document_id!=''",
                       (pid,)).fetchone()[0]
        address_id=address_key(city,address)
        strong=bool(city and (app or address_id))
        inactive=bool(INACTIVE.search(stage or ""))
        publish=strong and bool(url) and not inactive and (n>0 or doc>0)
        state="RESEARCH_CANDIDATE" if publish else "REVIEW_REQUIRED"
        missing=[]
        if not strong:missing.append("IDENTITY_UNCERTAIN")
        if not url:missing.append("SOURCE_URL_MISSING")
        if inactive:missing.append("INACTIVE_STAGE")
        if n==0 and doc==0:missing.append("NO_SOURCE_EVIDENCE")
        # A research candidate is NOT a verified customer or open contract.
        db.execute("""UPDATE project_nodes SET source_count=?,review_state=?,
                  review_reason=?,updated_at=? WHERE project_id=?""",
                  (n+doc,state,";".join(missing),now,pid))
        if address_id:
            by_address[address_id].append(pid)
    for addr, members in by_address.items():
        if not (1<len(members)<=10):
            continue
        members=sorted(set(members))
        for i,left in enumerate(members):
            for right in members[i+1:]:
                # Even exact addresses are NOT sufficient to auto-merge projects.
                city=addr.split("|",1)[0]
                db.execute("""INSERT OR IGNORE INTO project_review_links
                    VALUES(?,?,?,?,?,?)""",
                    (left,right,addr.split("|",1)[-1],city,
                     "REVIEW_REQUIRED","SAME_NUMBERED_ADDRESS_NOT_PROOF_SAME_PROJECT"))


def write_csv(path, columns, rows):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as handle:
        w=csv.writer(handle)
        w.writerow(columns)
        w.writerows(rows)


def build(home):
    home=Path(home).expanduser().resolve()
    master=workspace.setup(home)
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(sqlite3.connect(master,timeout=30)) as db:
        db.execute("PRAGMA busy_timeout=30000")
        setup(db)
        # Keep raw records and versions. Only refresh our derived engine tables.
        for table in ("project_review_links","project_facts","project_record_edges",
                      "project_nodes"):
            db.execute("DELETE FROM "+table)
        source_records=ingest_records(db,now)
        documents=read_documents(db,home,now)
        finalize(db,now)
        rows=list(db.execute("""SELECT project_id,city,address,application_id,
           description,stage,first_observed_at,source_date,date_basis,source_count,
           source_url,review_state,review_reason FROM project_nodes
           ORDER BY review_state,first_observed_at DESC LIMIT 10000"""))
        linkrows=list(db.execute("""SELECT left_project_id,right_project_id,address,
           city,status,reason FROM project_review_links ORDER BY city,address LIMIT 5000"""))
        docrows=list(db.execute("""SELECT document_id,filename,document_type,
           extraction_status,LENGTH(extracted_text),source_url,reason
           FROM project_documents ORDER BY filename LIMIT 5000"""))
        counts=dict(db.execute("SELECT review_state,COUNT(*) FROM project_nodes GROUP BY review_state"))
        db.commit()
    results=home/"Results"
    for target,filterstate in ((PROJECT_FILE,"RESEARCH_CANDIDATE"),(REVIEW_FILE,"REVIEW_REQUIRED")):
        export=[]
        for r in rows:
            if r[11]!=filterstate:
                continue
            export.append((*r[:11],r[11],r[12],
                           "UNVERIFIED","UNKNOWN"))
        write_csv(results/target,FIELDS,export)
    write_csv(results/LINK_FILE,LINK_FIELDS,linkrows)
    write_csv(results/DOCUMENT_FILE,DOCUMENT_FIELDS,docrows)
    return {"status":"SUCCESS","indexed_source_records":source_records,
            "documents_checked":documents,
            "research_candidates":counts.get("RESEARCH_CANDIDATE",0),
            "needs_review":counts.get("REVIEW_REQUIRED",0),
            "possible_links_for_review":len(linkrows),
            "buyer_verification":"NOT_PERFORMED","deepseek_calls":0}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--home",required=True)
    p.add_argument("action",choices=["build"])
    args=p.parse_args(argv)
    print(json.dumps(build(args.home),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
