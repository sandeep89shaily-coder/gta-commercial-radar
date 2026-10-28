"""Collect verified public Toronto report PDFs without crawling secure.toronto.ca.

Each queue item must include an independently observed official meeting/item
source and an exact report PDF URL. This adapter does not discover new meeting
agenda items automatically and does not touch V8 or invoke paid AI.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from toronto_pdf_download import fetch_one, valid_url

COLUMNS=("agenda_or_item_url","attachment_url","source_label","evidence_status")
AUDIT=("agenda_or_item_url","attachment_url","source_label","status","reason","http_status","bytes","sha256","saved_path")
OFFICIAL={"secure.toronto.ca","www.toronto.ca"}

def validate_row(row):
    source=str(row.get("agenda_or_item_url") or "").strip()
    p=urlparse(source)
    if p.scheme!="https" or p.hostname not in OFFICIAL or p.username or p.password or p.port not in (None,443):
        return "INVALID_OFFICIAL_EVIDENCE_URL"
    if not valid_url(str(row.get("attachment_url") or "").strip()):
        return "INVALID_PDF_URL"
    if row.get("evidence_status")!="OFFICIAL_PAGE_LINK_OBSERVED":
        return "SOURCE_EVIDENCE_NOT_VERIFIED"
    return ""

def run(queue_csv, output, *, fetch=False, max_files=6, downloader=fetch_one):
    target=Path(output);target.mkdir(parents=True,exist_ok=True)
    with Path(queue_csv).open(encoding="utf-8-sig",newline="") as h:
        reader=csv.DictReader(h)
        if any(c not in (reader.fieldnames or []) for c in COLUMNS):
            raise ValueError("Required evidence queue fields missing")
        rows=list(reader)
    attempts=[];seen=set()
    for row in rows:
        pdf=str(row.get("attachment_url") or "").strip()
        if pdf in seen:continue
        seen.add(pdf)
        if len(attempts)>=max(0,min(int(max_files),20)):break
        issue=validate_row(row)
        record={"agenda_or_item_url":row.get("agenda_or_item_url",""),
                "attachment_url":pdf,"source_label":row.get("source_label",""),
                "status":"SKIPPED","reason":issue or "DRY_RUN","http_status":"",
                "bytes":0,"sha256":"","saved_path":""}
        if not issue and fetch:
            filename=hashlib.sha256(pdf.encode()).hexdigest()[:24]+".pdf"
            found=downloader(pdf,target/"pdfs"/filename)
            record.update({key:found.get(key,record.get(key)) for key in ("status","reason","http_status","bytes","sha256","saved_path")})
        attempts.append(record)
    with (target/"VERIFIED_REPORT_FETCH_AUDIT.csv").open("w",encoding="utf-8-sig",newline="") as h:
        writer=csv.DictWriter(h,fieldnames=AUDIT);writer.writeheader();writer.writerows(attempts)
    summary={"queue_unique_checked":len(attempts),
             "captured":sum(x["status"]=="CAPTURED" for x in attempts),
             "failed_or_skipped":sum(x["status"]!="CAPTURED" for x in attempts),
             "automatic_agenda_discovery":False,
             "paid_ai_calls":0,
             "audit":str((target/"VERIFIED_REPORT_FETCH_AUDIT.csv").resolve())}
    (target/"VERIFIED_REPORT_FETCH_SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--queue",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--fetch",action="store_true")
    p.add_argument("--max-files",type=int,default=6)
    a=p.parse_args()
    print(json.dumps(run(a.queue,a.out,fetch=a.fetch,max_files=a.max_files),indent=2))

if __name__=="__main__": main()
