"""Bounded, free verification of purchasing evidence for existing Radar candidates.

Reads explicit, sourced candidate observations. It never discovers fictitious
contacts, assumes no award means open, or sets sale_ready. Real pages are fetched
through the existing robots-respecting source client. Network failures are recorded.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,json
from pathlib import Path
from urllib.parse import urlparse
import auto_verify

KINDS={"BUYER_ORGANIZATION","BUYING_AUTHORITY","PUBLIC_CONTACT_ROUTE",
       "CURRENT_CONTRACTOR","PROCUREMENT_PACKAGE","SUPPLIER_AWARD"}
VALID_STATES={"TENDER_OPEN","FUTURE_PROCUREMENT_CONFIRMED","AWARDED","NOT_AWARDED_AFFIRMATIVE","UNKNOWN"}
COLUMNS=("project_id","kind","organization","source_url","excerpt","observed_date",
         "package","status","contact_url","role")
def valid_row(row):
    if not row.get("project_id"):return row.get("lineage") or "MISSING_PROJECT_ID"
    if row.get("kind") not in KINDS:return "INVALID_KIND"
    if not str(row.get("source_url") or "").startswith("https://"):return "NO_HTTPS_SOURCE"
    if len(str(row.get("excerpt") or "").strip())<25:return "NO_QUOTED_EVIDENCE"
    if row.get("kind") in ("PROCUREMENT_PACKAGE","SUPPLIER_AWARD") and row.get("status","UNKNOWN") not in VALID_STATES:
        return "INVALID_PACKAGE_STATUS"
    return ""
def inspect(rows,fetcher=auto_verify.fetch_page,limit=30):
    results=[];cache={}
    for row in rows[:limit]:
        item={k:row.get(k,"") for k in COLUMNS}
        item["lineage"]=row.get("lineage","")
        item["input_origin"]=row.get("input_origin","")
        item.update(proof_status="UNVERIFIED",purchasing_authority_verified=False,
                    unawarded_package_verified=False,source_match=False)
        issue=valid_row(row)
        if issue:item["reason"]=issue;results.append(item);continue
        url=row["source_url"]
        if url not in cache:cache[url]=fetcher(url)
        fetched=cache[url]
        if not fetched.get("ok"):
            item.update(proof_status="INCONCLUSIVE",reason=fetched.get("reason","FETCH_FAILED"))
            results.append(item);continue
        match=auto_verify.excerpt_present(fetched.get("text",""),row["excerpt"])
        item["source_match"]=match
        if not match:
            item.update(proof_status="REJECTED",reason="EXCERPT_NOT_ON_SOURCE")
        else:
            item.update(proof_status="SOURCE_TEXT_MATCHED",reason="PROJECT_AND_PROCUREMENT_CONTEXT_NEEDS_REVIEW")
            # Text matching proves that the source says something, not that it
            # applies to the current phase or that contract status is true today.
            if row["kind"] in ("PROCUREMENT_PACKAGE","SUPPLIER_AWARD"):
                item["reason"]="SOURCE_QUOTE_MATCHED_AWARD_STATUS_REQUIRES_HUMAN_REVIEW"
            elif row["kind"]=="BUYING_AUTHORITY":
                item["reason"]="SOURCE_QUOTE_MATCHED_AUTHORITY_REQUIRES_HUMAN_REVIEW"
        results.append(item)
    return results
def _source_project_index(review):
    """Exact URLs map to sets of project IDs; shared URLs cannot resolve identity."""
    index={}
    if not review:
        return index
    for path in sorted(Path(review).glob("AI_PROJECT_*.json")):
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError,TypeError):
            continue
        pid=str(data.get("project_id") or "").strip()
        if not pid:
            continue
        for source in data.get("sources",[]):
            if not isinstance(source,dict):
                continue
            url=str(source.get("url") or "").strip()
            if url:
                index.setdefault(url,set()).add(pid)
    return index

def source_rows(results=None,review=None):
    """Retain missing project IDs for diagnostic output, never discard silently."""
    rows=[]
    if results:
        candidate=Path(results)/"PURCHASING_EVIDENCE_CANDIDATES.csv"
        if candidate.is_file():
            with candidate.open(encoding="utf-8-sig",newline="") as f:
                rows.extend({**row,"input_origin":"PURCHASING_EVIDENCE_CANDIDATES"} for row in csv.DictReader(f))
    if review:
        path=Path(review)/"BUYER_RELATIONSHIPS_REVIEW.json"
        try:
            observations=json.loads(path.read_text(encoding="utf-8")).get("observations",[])
        except (OSError,ValueError,TypeError,AttributeError):
            observations=[]
        index=_source_project_index(review)
        for item in observations:
            if not isinstance(item,dict):
                continue
            url=str(item.get("source_url") or "").strip()
            quote=str(item.get("exact_quote") or "").strip()
            if not url and not quote:
                continue
            pid=str(item.get("project_id") or "").strip()
            lineage="PROJECT_ID_FROM_EXTRACTOR" if pid else "MISSING_PROJECT_ID"
            if not pid and url:
                matches=index.get(url,set())
                if len(matches)==1:
                    pid=next(iter(matches))
                    lineage="UNIQUE_EXACT_SOURCE_URL_RECONCILIATION"
                elif len(matches)>1:
                    lineage="AMBIGUOUS_SOURCE_URL_PROJECT"
            rows.append({"project_id":pid,"kind":"BUYING_AUTHORITY",
                "organization":item.get("organization",""),
                "source_url":url,"excerpt":quote,
                "role":item.get("role",""),"status":"UNKNOWN",
                "lineage":lineage,"input_origin":"BUYER_RELATIONSHIPS_REVIEW"})
    return rows

def execute(infile,out,limit=30,fetcher=auto_verify.fetch_page,review=None,results=None):
    if infile:
        with Path(infile).open(encoding="utf-8-sig",newline="") as f:
            rows=list(csv.DictReader(f))
    else:
        rows=source_rows(results,review)
    records=inspect(rows,fetcher,limit)
    report={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "records_checked":len(records),
            "input_observations":len(rows),
            "unlinked_observations":sum(not r.get("project_id") for r in rows),
            "reconciled_unique_source_urls":sum(r.get("lineage")=="UNIQUE_EXACT_SOURCE_URL_RECONCILIATION" for r in rows),
            "status":("NO_BUYER_EVIDENCE_INPUT" if not rows else
                "NO_SOURCE_TEXT_MATCH" if not any(x["source_match"] for x in records) else
                "SOURCE_EVIDENCE_FOR_REVIEW"),
            "source_text_matches":sum(x["source_match"] for x in records),
            "inconclusive":sum(x["proof_status"]=="INCONCLUSIVE" for x in records),
            "verified_buying_authorities":0,"verified_unawarded_packages":0,
            "paid_ai_calls":0,"source_databases_modified":False,"records":records}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    (out/("LIVE_PROCUREMENT_EVIDENCE_"+stamp+".json")).write_text(json.dumps(report,indent=2),encoding="utf-8")
    with (out/("LIVE_PROCUREMENT_EVIDENCE_"+stamp+".csv")).open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]) if records else list(COLUMNS))
        writer.writeheader();writer.writerows(records)
    return report
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input");p.add_argument("--results");p.add_argument("--review");p.add_argument("--out",required=True)
    p.add_argument("--limit",type=int,default=30)
    a=p.parse_args()
    if not 1<=a.limit<=30:p.error("limit must be 1..30")
    print(json.dumps({k:v for k,v in execute(a.input,a.out,a.limit,review=a.review,results=a.results).items() if k!="records"},indent=2))
if __name__=="__main__":main()
