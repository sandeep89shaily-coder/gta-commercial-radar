"""Evidence-cited Toronto staff-report facts from already-local PDFs.

Extract only explicit document facts, retaining page, excerpt and SHA256.
Report date is NOT public posting date. A staff contact is NOT a purchaser.
No network, no AI, no automatic sales qualification.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from pathlib import Path
from toronto_tmmis_documents import extract_local_pdf

FIELDS=["document_url","sha256","page","field","value","excerpt",
        "verification_status","source_publication_date","buyer_verified",
        "supplier_award_verified"]
PATTERNS={
    "planning_application_number": re.compile(
        r"Planning Application Number\s*:\s*([0-9][0-9 ]{4,28}[A-Z]{1,4}(?:\s*[0-9A-Z]{1,4})?)",re.I),
    "report_date": re.compile(
        r"\bDate\s*:\s*((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2})\b",re.I),
    "ward": re.compile(r"\bWard\s*:\s*(\d{1,2}\s*-\s*[^\n]{4,90})",re.I),
}
MAX_PER_FIELD=3


def extract_facts(pages, pdf_sha256, document_url=""):
    facts=[]
    for page in pages:
        body=str(page.get("text") or "")
        number=page.get("page")
        for name,regex in PATTERNS.items():
            for m in list(regex.finditer(body))[:MAX_PER_FIELD]:
                value=" ".join(m.group(1).split())
                excerpt=" ".join(body[max(0,m.start()-80):min(len(body),m.end()+120)].split())
                facts.append({"document_url":document_url,"sha256":pdf_sha256,
                              "page":number,"field":name,"value":value,
                              "excerpt":excerpt[:300],
                              "verification_status":"SOURCE_TEXT_UNVERIFIED",
                              "source_publication_date":"",
                              "buyer_verified":"NO",
                              "supplier_award_verified":"NO"})
    return facts


def run(pdf, out, url=""):
    read=extract_local_pdf(pdf)
    facts=extract_facts(read["pages"],read["sha256"],url)
    target=Path(out)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("w",encoding="utf-8-sig",newline="") as handle:
        w=csv.DictWriter(handle,fieldnames=FIELDS)
        w.writeheader()
        w.writerows(facts)
    summary={"pages":len(read["pages"]),"facts_for_review":len(facts),
             "requires_ocr_review":read["requires_ocr_review"],
             "publication_date_verified":False,
             "buyer_verified":False,
             "supplier_award_verified":False,
             "paid_ai_calls":0,
             "source_sha256":read["sha256"]}
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pdf",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--source-url",default="")
    a=p.parse_args()
    print(json.dumps(run(a.pdf,a.out,a.source_url),indent=2))


if __name__=="__main__":
    main()
