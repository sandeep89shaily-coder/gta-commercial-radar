"""Toronto meeting-schedule discovery from the City's licensed CKAN dataset.

Schedule entries are only event candidates; they do NOT establish TMMIS
agenda URLs, report links, publication dates, or approved automated agenda
access. Read public official CKAN metadata/data, emit triage records.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,json,hashlib
from pathlib import Path
from urllib.parse import urlparse
import requests

API="https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
DATASET="3bfab808-105b-45ab-8d92-cf1916594653"
RESOURCE="meeting-schedule-all-committees-2022-2026"
MAX_SIZE=2_000_000
FIELDS=("source_name","meeting_name","meeting_date","committee_relevance",
        "meeting_url","agenda_status","document_status","retrieval_status")
WORDS=("planning","community council","city council","development","housing","economic",
       "committee of adjustment")

def select_resource(metadata):
    result=metadata.get("result") or {}
    if not metadata.get("success") or not isinstance(result,dict):
        raise ValueError("CKAN metadata success missing")
    for item in result.get("resources",[]):
        if RESOURCE in str(item.get("name","")).lower():
            url=str(item.get("url") or "")
            p=urlparse(url)
            if p.scheme!="https" or not p.hostname or p.username or p.password:
                raise ValueError("Unapproved resource URL")
            # Toronto-owned resources only, not redirects to arbitrary third parties.
            if not (p.hostname=="toronto.ca" or p.hostname.endswith(".toronto.ca")
                    or p.hostname=="ckan0.cf.opendata.inter.prod-toronto.ca"):
                raise ValueError("Resource host not Toronto")
            return url
    raise ValueError("Expected 2022-2026 meeting schedule resource missing")

def import_csv(content):
    import io
    text=content.decode("utf-8-sig")
    rows=list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("Empty CSV")
    columns=list(rows[0].keys())
    def column(*terms):
        return next((k for k in columns if k and all(t in k.lower() for t in terms)),None)
    date=column("date")
    name=next((k for k in columns if k and ("meeting" in k.lower() or "committee" in k.lower()) and "date" not in k.lower() and "time" not in k.lower()),None)
    if not date or not name:
        raise ValueError("Unexpected official schedule CSV columns: "+str(columns))
    output=[];seen=set()
    for row in rows:
        meeting=" ".join(str(row.get(name) or "").split())[:160]
        raw_date=str(row.get(date) or "").strip()
        if not meeting or not raw_date:continue
        parsed=""
        for fmt in ("%Y-%m-%d","%m/%d/%Y","%Y-%m-%dT%H:%M:%S","%d/%m/%Y"):
            try:parsed=dt.datetime.strptime(raw_date[:19],fmt).date().isoformat();break
            except ValueError:pass
        if not parsed:
            # Failed dates are not silently replaced with ingestion dates.
            continue
        identity=(parsed,meeting.lower())
        if identity in seen:continue
        seen.add(identity)
        relevant=any(w in meeting.lower() for w in WORDS)
        output.append({"source_name":"Toronto Open Data TMMIS meeting schedule",
                       "meeting_name":meeting,"meeting_date":parsed,
                       "committee_relevance":"REVIEW_PRIORITY" if relevant else "OTHER",
                       "meeting_url":"","agenda_status":"NOT_RESOLVED",
                       "document_status":"NOT_DISCOVERED",
                       "retrieval_status":"OFFICIAL_SCHEDULE_ONLY"})
    return output

def write(rows,out,metadata):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with (out/"TORONTO_SCHEDULE_MEETINGS_REVIEW.csv").open("w",encoding="utf-8-sig",newline="") as h:
        writer=csv.DictWriter(h,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    summary={"schedule_entries":len(rows),"review_priority":sum(x["committee_relevance"]=="REVIEW_PRIORITY" for x in rows),
             "agenda_urls_verified":0,"agenda_documents_downloaded":0,"paid_ai_calls":0,
             "source":metadata}
    (out/"TORONTO_SCHEDULE_SOURCE_AUDIT.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary

def fetch_official(out,*,session=None):
    session=session or requests.Session()
    session.trust_env=False
    def bounded(url,bytes_limit):
        response=session.get(url,timeout=(10,30),allow_redirects=False,stream=True)
        with response as r:
            if r.status_code!=200 or r.url!=url:
                raise ValueError("HTTP/redirect rejected: "+str(r.status_code))
            content=bytearray()
            for piece in r.iter_content(65536):
                content.extend(piece)
                if len(content)>bytes_limit:raise ValueError("Resource too large")
            return bytes(content)
    metadata=json.loads(bounded(API+"?id="+DATASET,800_000))
    resource=select_resource(metadata)
    data=bounded(resource,MAX_SIZE)
    return write(import_csv(data),out,{"dataset":DATASET,"resource_url":resource,
                                        "sha256":hashlib.sha256(data).hexdigest(),
                                        "source_publication_date":"NOT_VERIFIED"})

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    p.add_argument("--csv",help="Previously obtained official Toronto schedule CSV")
    p.add_argument("--fetch-official",action="store_true",help="Opt in to CKAN metadata and dataset download")
    a=p.parse_args()
    if bool(a.csv)==bool(a.fetch_official):
        p.error("Choose exactly one of --csv or --fetch-official")
    if a.csv:
        content=Path(a.csv).read_bytes()
        summary=write(import_csv(content),a.out,
                      {"local_csv":str(a.csv),"sha256":hashlib.sha256(content).hexdigest()})
    else:
        summary=fetch_official(a.out)
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
