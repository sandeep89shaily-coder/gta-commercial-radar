"""Export Hamilton human-researched public business evidence as REVIEW ONLY.

There is no automatic vendor availability checking, no person contact enrichment,
and no fictitious verified buyer. Runs locally on checked-in public source notes.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse
from early_cue_watch import _write_csv

COLUMNS=("review_order","id","lane","organization","site","published_date",
 "published_date_type","reported_project_cost_cad","project_summary",
 "hypothetical_supplier_fits","public_business_contact","contact_role",
 "project_evidence_url","organization_corroboration_url","contact_evidence_url",
 "company_role","current_project_stage","purchasing_decision_maker",
 "vendor_selection_status","contract_availability","sale_ready","next_verification")
SUMMARY=("metric","value","notes")

def validate(entries):
    if not isinstance(entries,list) or not entries:
        raise RuntimeError("No researched Hamilton candidates")
    seen=set()
    for row in entries:
        rid=row.get("id")
        if not rid or rid in seen:
            raise RuntimeError("Missing or duplicate Hamilton research identity")
        seen.add(rid)
        if row.get("sale_ready") is not False:
            raise RuntimeError("Research seeds may NOT claim sale-ready status")
        for key in ("purchasing_decision_maker","vendor_selection_status","contract_availability"):
            if row.get(key) not in ("UNKNOWN","UNVERIFIED"):
                raise RuntimeError("Unverified purchasing data must stay unknown")
        uri=row.get("project_evidence_url") or ""
        url=urlparse(uri)
        if url.scheme!="https" or not url.hostname:
            raise RuntimeError("Research item lacks original public HTTPS source")
        date=row.get("published_date")
        if date is None:
            if row.get("published_date_type")!="PUBLIC_DATE_NOT_VERIFIED_FOR_CURRENT_SCOPE":
                raise RuntimeError("Unknown publication date must be labeled")
        else:
            from datetime import date as Date
            try:Date.fromisoformat(date)
            except (TypeError,ValueError) as exc:
                raise RuntimeError("Unparseable original published date") from exc
    return True

def run(seed="research/hamilton_public_business_evidence_20261024.json",
        output_dir="GTA_RADAR_RESULTS"):
    raw=json.loads(Path(seed).read_text(encoding="utf-8"))
    entries=raw["entries"]
    validate(entries)
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for e in entries:
        r={**e,
           "hypothetical_supplier_fits":"; ".join(e.get("hypothetical_supplier_fits",[])),
           "sale_ready":"NO"}
        rows.append(r)
    _write_csv(out/"HAMILTON_EVIDENCE_BACKED_COMPANY_RESEARCH.csv",COLUMNS,rows)
    _write_csv(out/"HAMILTON_EVIDENCE_STATUS.csv",SUMMARY,[
        dict(metric="company_project_research_records",value=len(entries),
             notes="Published project or funding scope plus publicly documented company contact"),
        dict(metric="planning_or_master_development_cases",
             value=sum(e["lane"] in ("EARLY_PLANNING","MASTER_DEVELOPMENT") for e in entries),
             notes="Earliest planning intention, not a verified unawarded trade"),
        dict(metric="funded_factory_upgrade_cases",
             value=sum(e["lane"]=="FUNDED_FACTORY_UPGRADE" for e in entries),
             notes="Funding announced, vendor status UNKNOWN, some equipment may already be purchased"),
        dict(metric="verified_purchasing_decision_makers",value=0,
             notes="General company emails are not verified procurement officers"),
        dict(metric="verified_unawarded_work_packages",value=0,
             notes="No independently verified supplier-selection proof"),
        dict(metric="sale_ready_verified_leads",value=0,
             notes="Project/company contact verification is not a contract opportunity")])
    print("Hamilton public business research",len(entries),
          "| formally verified purchasing officers 0 | sale-ready 0")
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed",default="research/hamilton_public_business_evidence_20261024.json")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args();raise SystemExit(run(a.seed,a.output_dir))
