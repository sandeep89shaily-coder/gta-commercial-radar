"""Bounded, auditable Toronto background-PDF downloader (review-only).

Only discovered, official TMMIS background PDFs. Explicit --fetch required.
Fail closed on robots unknown/disallow, DNS/private addresses, redirects,
invalid file signature, oversized files, and HTML error pages.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import ipaddress
import json
import os
import socket
import tempfile
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse
import requests

from toronto_tmmis_documents import ATTACHMENT, PDF_HOST

AGENT="GTARadarResearch/1.0 (+municipal document evidence pilot)"
MAX_BYTES=15_000_000
TIMEOUT=(8,25)
AUDIT_FIELDS=("url","status","reason","http_status","bytes","sha256","saved_path")
def valid_url(url):
    try:
        p=urlparse(url)
        return (p.scheme=="https" and p.hostname==PDF_HOST and
                p.port in (None,443) and not p.username and not p.password and
                not p.query and not p.fragment and bool(ATTACHMENT.fullmatch(p.path)))
    except ValueError:
        return False

def public_dns(host, resolver=socket.getaddrinfo):
    try:
        addresses=resolver(host,443,type=socket.SOCK_STREAM)
        ips={rec[4][0] for rec in addresses}
        return bool(ips) and all(ipaddress.ip_address(ip).is_global for ip in ips)
    except (OSError,ValueError):
        return False

def robots_allowed(url,session,*,get_policy=None):
    if get_policy is None:
        def get_policy(u):
            r=session.get(u,timeout=TIMEOUT,allow_redirects=False)
            if r.status_code!=200 or r.url!=u or len(r.content)>512_000:
                return None
            return r.text
    policy=get_policy("https://www.toronto.ca/robots.txt")
    if policy is None:
        return False,"ROBOTS_UNAVAILABLE"
    parser=urllib.robotparser.RobotFileParser()
    parser.parse(policy.splitlines())
    if not parser.can_fetch(AGENT,url):
        return False,"ROBOTS_DISALLOWED"
    return True,"ALLOWED"

def fetch_one(url,destination,*,session=None,resolver=socket.getaddrinfo,get_policy=None):
    outcome={"url":url,"status":"FAILED","reason":"","http_status":"","bytes":0,"sha256":"","saved_path":""}
    if not valid_url(url):
        outcome["reason"]="UNAPPROVED_URL";return outcome
    if not public_dns(PDF_HOST,resolver):
        outcome["reason"]="DNS_UNAVAILABLE_OR_NONPUBLIC";return outcome
    session=session or requests.Session()
    session.trust_env=False
    session.headers.update({"User-Agent":AGENT,"Accept":"application/pdf"})
    allowed,reason=robots_allowed(url,session,get_policy=get_policy)
    if not allowed:
        outcome["reason"]=reason;return outcome
    temp=None
    try:
        with session.get(url,timeout=TIMEOUT,allow_redirects=False,stream=True) as r:
            outcome["http_status"]=r.status_code
            if r.status_code!=200:
                outcome["reason"]="HTTP_"+str(r.status_code);return outcome
            if r.url!=url:
                outcome["reason"]="URL_CHANGED";return outcome
            mime=r.headers.get("Content-Type","").split(";",1)[0].strip().lower()
            if mime not in ("application/pdf","application/octet-stream"):
                outcome["reason"]="NOT_PDF_CONTENT_TYPE";return outcome
            length=r.headers.get("Content-Length")
            if length:
                try:
                    if int(length)>MAX_BYTES:
                        outcome["reason"]="TOO_LARGE";return outcome
                except ValueError:
                    outcome["reason"]="INVALID_LENGTH";return outcome
            dest=Path(destination);dest.parent.mkdir(parents=True,exist_ok=True)
            sha=hashlib.sha256();size=0;prefix=b""
            with tempfile.NamedTemporaryFile(dir=dest.parent,suffix=".part",delete=False) as tmp:
                temp=Path(tmp.name)
                for chunk in r.iter_content(chunk_size=65536):
                    if not chunk:continue
                    size+=len(chunk)
                    if size>MAX_BYTES:
                        outcome["reason"]="TOO_LARGE";return outcome
                    if len(prefix)<8:prefix=(prefix+chunk)[:8]
                    sha.update(chunk);tmp.write(chunk)
            if not prefix.startswith(b"%PDF-") or size<100:
                outcome["reason"]="INVALID_PDF_SIGNATURE";return outcome
            # pypdf inspection catches truncated/corrupt/HTML-disguised PDFs.
            try:
                from pypdf import PdfReader
                with temp.open("rb") as h:
                    pdf=PdfReader(h,strict=False)
                    if pdf.is_encrypted or len(pdf.pages)<1:
                        raise ValueError("Encrypted or empty PDF")
            except Exception:
                outcome["reason"]="INVALID_OR_ENCRYPTED_PDF";return outcome
            os.replace(temp,dest);temp=None
            outcome.update(status="CAPTURED",reason="OK",bytes=size,
                           sha256=sha.hexdigest(),saved_path=str(dest.resolve()))
            return outcome
    except requests.RequestException as exc:
        outcome["reason"]="NETWORK_"+type(exc).__name__;return outcome
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)

def batch(input_csv,out_dir,*,fetch=False,max_files=3,session=None,resolver=socket.getaddrinfo,get_policy=None):
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    with Path(input_csv).open(encoding="utf-8-sig",newline="") as h:
        rows=list(csv.DictReader(h))
    results=[];unique=set()
    for row in rows:
        url=str(row.get("attachment_url") or "").strip()
        if not url or url in unique:continue
        unique.add(url)
        if len(results)>=max_files:break
        if not fetch:
            results.append(dict(url=url,status="DRY_RUN",reason="EXPLICIT_FETCH_REQUIRED",
                                http_status="",bytes=0,sha256="",saved_path=""))
            continue
        name=hashlib.sha256(url.encode()).hexdigest()[:24]+".pdf"
        results.append(fetch_one(url,out/"pdfs"/name,session=session,
                                 resolver=resolver,get_policy=get_policy))
    audit=out/"TORONTO_PDF_FETCH_AUDIT.csv"
    with audit.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=AUDIT_FIELDS);w.writeheader();w.writerows(results)
    return {"attempted":len(results),"captured":sum(x["status"]=="CAPTURED" for x in results),
            "audit":str(audit.resolve()),"paid_ai_calls":0,
            "results":[{"url":r["url"],"status":r["status"],"reason":r["reason"]} for r in results]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--discovered-csv",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--max-files",type=int,default=3)
    p.add_argument("--fetch",action="store_true")
    args=p.parse_args()
    print(json.dumps(batch(args.discovered_csv,args.out,fetch=args.fetch,
                           max_files=max(0,min(args.max_files,10))),indent=2))

if __name__=="__main__":
    main()
