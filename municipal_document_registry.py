"""Validate official municipal document source registry without network/AI.

Index confirmed is not a successfully fetched document. Output files are
review-only and can safely be regenerated without touching production data.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REQUIRED = ("id","city","url","system","source_type","priority","evidence","status","publish")
ALLOWED = {"Toronto","Brampton","Mississauga","Hamilton"}
PREFIX = "OFFICIAL_INDEX_CONFIRMED_"


def validate(source):
    with Path(source).open(encoding="utf-8-sig", newline="") as h:
        reader=csv.DictReader(h)
        if not reader.fieldnames or any(field not in reader.fieldnames for field in REQUIRED):
            raise ValueError("Registry fields missing")
        data=list(reader)
    seen=set()
    validated=[]
    for item in data:
        sid=item["id"].strip()
        if not sid or sid in seen:
            raise ValueError("Missing or duplicate source id")
        seen.add(sid)
        if item["city"] not in ALLOWED:
            raise ValueError("Unexpected municipality")
        for key in ("url","evidence"):
            uri=urlparse(item[key])
            if uri.scheme != "https" or not uri.netloc or uri.username or uri.password:
                raise ValueError("Official link must use HTTPS")
        if not item["status"].startswith(PREFIX):
            raise ValueError("Do not imply retrieval or commercial reuse approval")
        try:
            priority=int(item["priority"])
        except ValueError as exc:
            raise ValueError("Priority must be integer") from exc
        if priority < 1 or priority > 3:
            raise ValueError("Priority outside 1..3")
        validated.append(item)
    return validated


def report(source, destination):
    data=validate(source)
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    result={"registered_sources":len(data),
            "municipalities":sorted({r["city"] for r in data}),
            "documents_retrieved":0,
            "verified_publisher_dates":0,
            "commercial_reuse_permissions_confirmed":0,
            "automated_source_fetch_approved":0,
            "next_gate":"Verify concrete dated agenda/report documents per municipality, access policy, content type and reuse rules",
            "records":data}
    (destination/"MUNICIPAL_DOCUMENT_REGISTRY_STATUS.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=ROOT/"config"/"municipal_document_sources.csv")
    p.add_argument("--out",type=Path,default=ROOT/"document_source_review")
    a=p.parse_args()
    print(json.dumps(report(a.source,a.out),indent=2))


if __name__=="__main__":
    main()
