"""Review-only Toronto meeting -> agenda -> PDF pipeline.

Seed meeting URLs must come from observed TMMIS links, not guessed meeting IDs.
Use existing official link parser and validated PDF downloader. No paid AI,
V8 database mutation or unattended scheduling.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from toronto_tmmis_documents import agenda_url, parse_agenda, FIELDS
from toronto_pdf_download import AGENT, TIMEOUT, public_dns, fetch_one, AUDIT_FIELDS

SEEDS=("meeting_url",)
MEETING_AUDIT=("meeting_url","status","reason","pdf_links")
MAX_AGENDAS=6
MAX_FILES=12
MAX_HTML_BYTES=3_000_000

def meeting_access(url, session, *, resolver=None, policy_reader=None):
    if not agenda_url(url):
        return False,"UNAPPROVED_AGENDA_URL"
    host=urlparse(url).hostname
    if not public_dns(host, resolver or __import__("socket").getaddrinfo):
        return False,"DNS_UNAVAILABLE_OR_NONPUBLIC"
    robots_url="https://secure.toronto.ca/robots.txt"
    try:
        if policy_reader:
            policy=policy_reader(robots_url)
        else:
            r=session.get(robots_url,timeout=TIMEOUT,allow_redirects=False)
            policy=r.text if r.status_code==200 and r.url==robots_url and len(r.content)<=512000 else None
        if policy is None:
            return False,"ROBOTS_UNAVAILABLE"
        robot=RobotFileParser();robot.parse(policy.splitlines())
        return (True,"OK") if robot.can_fetch(AGENT,url) else (False,"ROBOTS_DISALLOWED")
    except requests.RequestException:
        return False,"ROBOTS_NETWORK_FAILURE"

def run(seed_csv,output,*,fetch=False,max_agendas=4,max_pdfs=6,session=None,
        resolver=None,meeting_policy=None,pdf_policy=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with Path(seed_csv).open(encoding="utf-8-sig",newline="") as h:
        reader=csv.DictReader(h)
        if "meeting_url" not in (reader.fieldnames or []):
            raise ValueError("Missing meeting_url")
        seeds=list(reader)
    session=session or requests.Session()
    session.trust_env=False
    session.headers["User-Agent"]=AGENT
    reports=[];meetings=[];seen=set()
    for seed in seeds:
        url=str(seed.get("meeting_url") or "").strip()
        if not url or url in seen:continue
        seen.add(url)
        if len(meetings)>=min(max(0,max_agendas),MAX_AGENDAS):break
        record={"meeting_url":url,"status":"SKIPPED","reason":"","pdf_links":0}
        if not agenda_url(url):
            record["reason"]="UNAPPROVED_AGENDA_URL";meetings.append(record);continue
        if not fetch:
            record.update(status="DRY_RUN",reason="EXPLICIT_FETCH_REQUIRED")
            meetings.append(record);continue
        ok,why=meeting_access(url,session,resolver=resolver,policy_reader=meeting_policy)
        if not ok:
            record["reason"]=why;meetings.append(record);continue
        try:
            with session.get(url,timeout=TIMEOUT,allow_redirects=False,stream=True) as response:
                if response.status_code!=200 or response.url!=url:
                    record["reason"]="HTTP_OR_REDIRECT_"+str(response.status_code)
                    meetings.append(record);continue
                mime=response.headers.get("Content-Type","").split(";")[0].lower()
                if mime not in ("text/html","application/xhtml+xml"):
                    record["reason"]="NOT_HTML";meetings.append(record);continue
                data=bytearray()
                for piece in response.iter_content(65536):
                    data.extend(piece)
                    if len(data)>MAX_HTML_BYTES:break
                if len(data)>MAX_HTML_BYTES:
                    record["reason"]="HTML_TOO_LARGE";meetings.append(record);continue
                links=parse_agenda(data.decode("utf-8","replace"),url)
                reports.extend(links)
                record.update(status="FETCHED",reason="OK",pdf_links=len(links))
        except requests.RequestException as error:
            record["reason"]="NETWORK_"+type(error).__name__
        meetings.append(record)
    # Deduplicate PDF links across meetings, while retaining the first meeting evidence.
    pdfs=[];downloaded=set()
    for row in reports:
        link=row["attachment_url"]
        if link in downloaded:continue
        downloaded.add(link)
        if len(pdfs)>=min(max(0,max_pdfs),MAX_FILES):break
        if fetch:
            filename=hashlib.sha256(link.encode()).hexdigest()[:24]+".pdf"
            pdfs.append(fetch_one(link,out/"pdfs"/filename,session=session,
                                  resolver=resolver or __import__("socket").getaddrinfo,
                                  get_policy=pdf_policy))
    for name,fields,rows in (("TORONTO_MEETING_AUDIT.csv",MEETING_AUDIT,meetings),
                             ("TORONTO_DISCOVERED_PDFS.csv",FIELDS,reports),
                             ("TORONTO_PDF_FETCH_AUDIT.csv",AUDIT_FIELDS,pdfs)):
        with (out/name).open("w",encoding="utf-8-sig",newline="") as h:
            writer=csv.DictWriter(h,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    summary={"meetings_attempted":len(meetings),"meetings_fetched":sum(x["status"]=="FETCHED" for x in meetings),
             "pdf_links_discovered":len(reports),"pdf_downloaded":sum(x["status"]=="CAPTURED" for x in pdfs),
             "pdf_failed":sum(x["status"]!="CAPTURED" for x in pdfs),
             "paid_ai_calls":0,"output_folder":str(out.resolve())}
    (out/"TORONTO_MEETING_PDF_SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--meetings",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--fetch",action="store_true")
    parser.add_argument("--max-agendas",type=int,default=4)
    parser.add_argument("--max-pdfs",type=int,default=6)
    args=parser.parse_args()
    print(json.dumps(run(args.meetings,args.out,fetch=args.fetch,
                         max_agendas=args.max_agendas,max_pdfs=args.max_pdfs),indent=2))
if __name__=="__main__":
    main()
