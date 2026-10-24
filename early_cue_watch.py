"""Free public early cues, independently baselined. No V8/scheduler/DeepSeek use.

This pilot monitors IESO's connection queue plus *specific* municipal project
pages. It does not claim complete geographic coverage or current procurement.
Failed/partial sources never replace historical data or generate fake alerts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

IESO_URL = "https://www.ieso.ca/Sector-Participants/Connection-Process/Application-Status"
# These verified Burlington URLs are SEEDS, not a full municipal development index.
BURLINGTON_PROJECT_URLS = (
    "https://www.burlington.ca/en/news/current-development-projects/3056376-canada-inc-777guelphline.aspx",
    "https://www.burlington.ca/en/news/current-development-projects/1376-1382-plains-rd-e.aspx",
    "https://www.burlington.ca/en/news/current-development-projects/2076-old-lakeshore-rd.aspx",
)
SOURCES = ("ieso_connections", "burlington_project_pages")
STATUS_COLUMNS = ("source_id", "state", "scope", "fetched", "new", "updated",
                  "baseline", "error", "warning")
EVENT_COLUMNS = ("observed_at", "change_type", "source_id", "record_id", "title",
                 "site", "company", "company_role", "stage", "signal_type",
                 "source_date", "first_seen_at", "source_url", "commercial_fit",
                 "procurement_status", "verification")
QUEUE_COLUMNS = ("source_id", "record_id", "title", "site", "company", "company_role",
                 "stage", "signal_type", "source_date", "first_seen_at",
                 "commercial_fit", "source_url", "procurement_status",
                 "verification", "first_appearance_status", "not_sale_ready_reason")
UA = "GTA-Radar-EarlyCueResearch/0.1 (+manual public data review)"
ALLOWED_HOSTS = {"www.ieso.ca", "ieso.ca", "www.burlington.ca"}
RELEVANT = re.compile(
    r"\b(?:industrial|warehouse|manufactur\w*|plant|factory|hotel|"
    r"cold[- ]storage|loading dock|retail|commercial|business park|"
    r"data cent(?:re|er)|power|electri\w*|generator|large load|"
    r"energy|transmission|hospital|logistic\w*|office)\b", re.I
)
GTA = re.compile(
    r"\b(?:Toronto|Brampton|Mississauga|Burlington|Vaughan|Markham|"
    r"Richmond Hill|Oakville|Milton|Ajax|Pickering|Whitby|Oshawa|"
    r"Scarborough|Etobicoke|North York|Peel|Halton|Durham|York Region)\b", re.I
)


def _txt(node):
    return " ".join(node.stripped_strings).strip() if node else ""


def fetch_html(session, url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Unexpected source host; refuse HTTP or untrusted URL")
    resp = session.get(url, headers={"User-Agent": UA}, timeout=(10, 40))
    resp.raise_for_status()
    # A login/challenge page must never be accepted as an empty GIS snapshot.
    raw = resp.text
    if len(raw) < 300 or "<html" not in raw[:5000].lower():
        raise RuntimeError("Unexpected or empty HTML response")
    return raw


def parse_ieso(html, url=IESO_URL):
    """Read the public HTML queue table. Any pagination must be flagged."""
    soup = BeautifulSoup(html, "html.parser")
    headings = ("CAA ID", "Applicant", "Name", "Type", "Size", "SIA Status")
    result = {}
    candidate_tables = []
    for table in soup.find_all("table"):
        tr = table.find("tr")
        if not tr:
            continue
        header = [ _txt(x) for x in tr.find_all(["th", "td"], recursive=False)]
        labels = " ".join(header).casefold()
        if sum(h.casefold() in labels for h in headings) >= 4:
            candidate_tables.append((table, header))
    if not candidate_tables:
        raise RuntimeError("IESO project table absent (possibly JavaScript-loaded); no data stored")
    if len(candidate_tables) > 1:
        raise RuntimeError("Multiple IESO tables matched; ambiguous snapshot")
    table, header = candidate_tables[0]
    def idx(name):
        for i, label in enumerate(header):
            if name.casefold() in label.casefold():
                return i
        raise RuntimeError("Missing IESO column: " + name)
    needed = {k:idx(k) for k in ("CAA ID", "Applicant", "Name", "Type", "Size")}
    optional = {k:next((i for i,h in enumerate(header)
                        if k.casefold() in h.casefold()), None)
                for k in ("Transmission Zone", "Proposed In-Service Date", "SIA Status")}
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["th","td"], recursive=False)
        if len(cells) < len(header):
            continue
        data = [_txt(c) for c in cells]
        cid = data[needed["CAA ID"]]
        # Public CAA IDs may contain queue subtype; don't fabricate a date from 2026.
        identifier = re.search(r"\b20\d{2}-[A-Z0-9-]{2,}\b", cid, re.I)
        if not identifier:
            continue
        ident = identifier.group(0).upper()
        if ident in result:
            raise RuntimeError("Duplicate IESO CAA identifier in source table")
        zone = data[optional["Transmission Zone"]] if optional["Transmission Zone"] is not None else ""
        stage = data[optional["SIA Status"]] if optional["SIA Status"] is not None else ""
        service = data[optional["Proposed In-Service Date"]] if optional["Proposed In-Service Date"] is not None else ""
        typ = data[needed["Type"]]
        name = data[needed["Name"]]
        size = data[needed["Size"]]
        applicant = data[needed["Applicant"]]
        info = " | ".join((name, typ, zone, size))
        result[ident] = {
            "source_id":"ieso_connections", "record_id":ident,
            "title":name, "site":zone, "company":applicant,
            "company_role":"PUBLISHED_IESO_APPLICANT_NOT_VERIFIED_BUYER",
            "stage":stage, "signal_type":typ, "source_date":"",
            "source_url":url, "commercial_fit":"REVIEW" if RELEVANT.search(info) else "LOW",
            "procurement_status":"UNKNOWN",
            "verification":"IESO_APPLICATION_NOT_CONTRACT",
            "attributes":{"size":size, "proposed_service":service}
        }
    if not result:
        raise RuntimeError("IESO table had no valid CAA applications")
    # The public UI may show only one page. Never claim comprehensive queue.
    text = soup.get_text(" ", strip=True)
    pagination = bool(re.search(r"\b\d+\s*[-–]\s*\d+\s+of\s+[\d,]+\b", text, re.I))
    return list(result.values()), ("PAGINATED_WINDOW_NOT_FULL_QUEUE" if pagination
                                    else "TABLE_PAGE_COVERAGE_UNVERIFIED")


def _line_after(lines, label):
    for i,line in enumerate(lines):
        if line.casefold().strip() == label.casefold() and i+1 < len(lines):
            return lines[i+1][:300]
    return ""


def parse_burlington(html, url):
    """One Burlington official project page; NOT municipality-wide discovery."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    title = _txt(heading)
    if not title or len(title) > 250:
        raise RuntimeError("Burlington project heading not found")
    whole = soup.get_text("\n", strip=True)
    if "Proposed Development" not in whole or "Site Address" not in whole:
        raise RuntimeError("Not a recognized Burlington development project page")
    lines = [line.strip() for line in whole.splitlines() if line.strip()]
    status = next((l.replace("Status - ","").strip() for l in lines
                   if l.startswith("Status - ")), "")
    site = next((lines[i+1] for i,l in enumerate(lines[:-1])
                 if re.search(r"\bWard\s+\d+\s+Site Address\b", l, re.I)), "")
    company = _line_after(lines,"Applicant") or _line_after(lines,"Proponent")
    marker = next((i for i,l in enumerate(lines)
                   if l == "Proposed Development"), -1)
    scope_lines=[]
    if marker >= 0:
        for line in lines[marker+1:]:
            if line.startswith(("Learn more","Planner", "File Numbers",
                                "Public Meetings","View the","Documents")):
                break
            scope_lines.append(line)
            if sum(len(x) for x in scope_lines)>700:
                break
    description = " ".join(scope_lines)[:850]
    if not description:
        raise RuntimeError("Burlington development description missing")
    match = re.search(r"(?im)Pre-Application Community Meeting", whole)
    # A meeting mention proves a stage in the public record, NOT a posting date.
    preapp = bool(match)
    record_id = urlparse(url).path.rsplit("/",1)[-1].casefold()
    if not record_id or not record_id.endswith(".aspx"):
        raise RuntimeError("Unrecognized Burlington project page URL")
    info = " ".join((title, description))
    return {
        "source_id":"burlington_project_pages", "record_id":record_id,
        "title":title, "site":site, "company":company,
        "company_role":"MUNICIPAL_PUBLISHED_APPLICANT_OR_PROPONENT_NOT_BUYER",
        "stage":status or "UNSPECIFIED", "signal_type":(
            "PRE_APPLICATION_MENTIONED" if preapp else "PROJECT_STATUS_PAGE"),
        "source_date":"", "source_url":url,
        "commercial_fit":"REVIEW" if RELEVANT.search(info) else "LOW",
        "procurement_status":"UNKNOWN",
        "verification":"PROJECT_PAGE_NOT_OPEN_PROCUREMENT",
        "attributes":{"proposal":description}
    }


def db_setup(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS snapshots (
        source_id TEXT NOT NULL, record_id TEXT NOT NULL,
        first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
        digest TEXT NOT NULL, content TEXT NOT NULL,
        PRIMARY KEY(source_id,record_id));
    CREATE TABLE IF NOT EXISTS changes (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, observed_at TEXT NOT NULL,
        source_id TEXT NOT NULL, record_id TEXT NOT NULL,
        change_type TEXT NOT NULL, content TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS cue_changes_time ON changes(observed_at);
    """)


def _hash(row):
    # Immutable first-seen is stored separately; only publisher fields are hashed.
    raw = json.dumps(row,sort_keys=True,ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def save_source(conn, source_id, items, observed):
    if not items or any(x["source_id"] != source_id for x in items):
        raise RuntimeError("Empty/mismatched source data: rejecting snapshot")
    if len({x["record_id"] for x in items}) != len(items):
        raise RuntimeError("Duplicate source identities: rejecting snapshot")
    existed = conn.execute("SELECT 1 FROM snapshots WHERE source_id=? LIMIT 1",
                           (source_id,)).fetchone() is not None
    new=updated=0
    for row in items:
        rid=row["record_id"]
        prior=conn.execute("SELECT first_seen_at,digest FROM snapshots "
                           "WHERE source_id=? AND record_id=?", (source_id,rid)).fetchone()
        digest=_hash(row)
        first_seen=prior[0] if prior else observed
        body=json.dumps(row,sort_keys=True,ensure_ascii=False)
        conn.execute("""INSERT INTO snapshots
          (source_id,record_id,first_seen_at,last_seen_at,digest,content)
          VALUES (?,?,?,?,?,?)
          ON CONFLICT(source_id,record_id)
          DO UPDATE SET last_seen_at=excluded.last_seen_at,
          digest=excluded.digest,content=excluded.content""",
          (source_id,rid,first_seen,observed,digest,body))
        change = "NEW" if prior is None else "UPDATED" if prior[1] != digest else None
        if change and existed:
            if change=="NEW":new+=1
            else:updated+=1
            conn.execute("INSERT INTO changes(observed_at,source_id,record_id,change_type,content) "
                         "VALUES (?,?,?,?,?)",(observed,source_id,rid,change,body))
    conn.commit()
    return {"new":new,"updated":updated,"baseline":"NO" if existed else "YES"}


def _write_csv(path, fields, data):
    tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("w",encoding="utf-8-sig",newline="") as stream:
        w=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore")
        w.writeheader()
        w.writerows(data)
    tmp.replace(path)


def run(data_dir="data",output_dir="GTA_RADAR_RESULTS",sources=None,session=None,
        observed=None,burlington_urls=None):
    data_dir=Path(data_dir);data_dir.mkdir(parents=True,exist_ok=True)
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    selected=set(sources or SOURCES)
    if not selected or selected-set(SOURCES):
        raise ValueError("Unknown early-cue source")
    session=session or requests.Session()
    now=observed or datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn=sqlite3.connect(data_dir/"early_cues_review.sqlite")
    db_setup(conn)
    statuses=[]
    try:
        for source in SOURCES:
            if source not in selected:continue
            try:
                if source=="ieso_connections":
                    html=fetch_html(session,IESO_URL)
                    items,warning=parse_ieso(html)
                    scope="IESO_VISIBLE_TABLE"
                else:
                    urls=tuple(burlington_urls or BURLINGTON_PROJECT_URLS)
                    if not urls:raise RuntimeError("No verified Burlington seed pages")
                    items=[parse_burlington(fetch_html(session,u),u) for u in urls]
                    warning="KNOWN_PROJECT_PAGES_ONLY_NOT_A_COMPLETE_CITY_FEED"
                    scope="KNOWN_PAGE_WATCH"
                result=save_source(conn,source,items,now)
                statuses.append(dict(source_id=source,state="SUCCESS",
                     scope=scope,fetched=len(items),warning=warning,error="",**result))
            except (ValueError,RuntimeError,requests.RequestException,
                    sqlite3.DatabaseError) as error:
                conn.rollback()
                statuses.append(dict(source_id=source,state="FAILED",
                     scope="NOT_VALIDATED",fetched=0,new=0,updated=0,
                     baseline="NO",warning="",error=str(error)[:250]))
        events=[]
        for stamp,typ,sid,rid,raw in conn.execute(
             "SELECT observed_at,change_type,source_id,record_id,content "
             "FROM changes WHERE observed_at=? ORDER BY event_id",(now,)):
            item=json.loads(raw)
            item.update(observed_at=stamp,change_type=typ)
            first=conn.execute("SELECT first_seen_at FROM snapshots "
                    "WHERE source_id=? AND record_id=?",(sid,rid)).fetchone()
            item["first_seen_at"]=first[0] if first else ""
            events.append(item)
        _write_csv(output_dir/"EARLY_CUES_CHANGES_REVIEW_ONLY.csv",EVENT_COLUMNS,events)
        _write_csv(output_dir/"EARLY_CUES_SOURCE_STATUS.csv",STATUS_COLUMNS,statuses)
        queue=[]
        for sid,rid,first,content in conn.execute(
              "SELECT source_id,record_id,first_seen_at,content FROM snapshots"):
            item=json.loads(content)
            if item.get("commercial_fit")!="REVIEW":continue
            queue.append(dict(**item,first_seen_at=first,
                   first_appearance_status="HISTORICAL_BASELINE_OR_FIRST_OBSERVATION",
                   not_sale_ready_reason="BUYER_ROLE_UNVERIFIED;VENDOR_STATUS_UNKNOWN;"
                      "PROCUREMENT_UNKNOWN;EARLINESS_NOT_PROVEN"))
        queue.sort(key=lambda x:(x["source_id"],x["record_id"]))
        _write_csv(output_dir/"EARLY_CUES_RESEARCH_QUEUE.csv",QUEUE_COLUMNS,queue)
        for s in statuses:
            print(s["source_id"],s["state"],"records=",s["fetched"],
                  "changes=",s["new"]+s["updated"],s["warning"],flush=True)
        print("Research candidates:",len(queue),
              "| No baseline records called NEW | No DeepSeek used")
        return 1 if any(s["state"]=="FAILED" for s in statuses) else 0
    finally:
        conn.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    p.add_argument("--source",action="append",choices=SOURCES)
    args=p.parse_args(argv)
    return run(args.data_dir,args.output_dir,args.source)


if __name__=="__main__":
    raise SystemExit(main())
