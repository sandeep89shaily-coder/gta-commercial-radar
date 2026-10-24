"""GTA Radar exact-scope stage audit: negative evidence without address conflation.

Human-verified evidence is saved as a controlled research input. One address
can contain an old withdrawn environmental proposal, a new industrial plan,
an active business, and an issued demolition permit simultaneously. Never
propagate an approval/withdrawal/contract to *all* projects at that address.

No contacts scraped, no AI, no scheduling, no V8 connection, no outreach.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

KEYS=("city","address","exact_scope_id")
FIELDS=("city","address","exact_scope_id","scope_label","actor","actor_role",
 "stage_assessment","project_specific_procurement","original_public_date",
 "event_date_basis","issue_to_resolve","primary_evidence_url",
 "relevant_source_count","distinct_other_scopes_same_site",
 "same_site_other_scopes","sale_ready")
EVENT_FIELDS=("check_id","city","address","exact_scope_id","event_type","event_date",
 "date_basis","stage_effect","actor","actor_role","procurement_status",
 "source_url","transfer_to_other_same_address_scopes")
PORTAL_FIELDS=("buyer_organization","kind","url","buyer_scope",
 "project_specific_open_bid_verified","vendor_signup_free","bid_document_may_require_vendor_account")
SCORE_FIELDS=("metric","value","meaning")

LATE_EVENTS={"ENVIRONMENTAL_APPROVAL_WITHDRAWN","CONTRACT_AWARDED",
 "CONSTRUCTION_COMPLETE","UNDER_CONSTRUCTION_PUBLIC_STATEMENT"}
EARLY_EVENTS={"FORMAL_CONSULTATION_GIS","COMPLETE_APPLICATION_PUBLIC_NOTICE",
 "PROPOSAL_FIRST_PUBLIC_POSTED"}
DATED_EVENT_TYPES={"PROPOSAL_FIRST_PUBLIC_POSTED","COMPLETE_APPLICATION_PUBLIC_NOTICE",
 "ENVIRONMENTAL_APPROVAL_WITHDRAWN","HISTORICAL_APPROVAL"}

def _https(value):
    p=urlparse(str(value or ""))
    return p.scheme=="https" and bool(p.hostname) and "." in p.hostname and not p.username and not p.password

def validate(document):
    checks=document.get("checks")
    if not isinstance(checks,list) or not checks:raise RuntimeError("No exact-scope records")
    seen=set()
    for row in checks:
        if not all(str(row.get(k) or "").strip() for k in KEYS):
            raise RuntimeError("Missing explicit city/address/application ID")
        scope=(row["city"].upper(),row["exact_scope_id"].upper())
        key=row.get("check_id")
        if not key or key in seen:raise RuntimeError("Duplicate/missing evidence check ID")
        seen.add(key)
        if row.get("transfer_to_other_same_address_scopes") is not False:
            raise RuntimeError("Cross-project stage transfer is forbidden")
        if not _https(row.get("source_url")):
            raise RuntimeError("Evidence must carry original HTTPS source")
        event_date=row.get("event_date")
        if event_date is not None:
            if row.get("date_basis")=="ONLY_2026_FILE_YEAR":
                raise RuntimeError("GIS filing year cannot be exact event date")
            if row.get("date_basis")=="CITY_PERMITS_ISSUED_MONTH_NOT_DAY":
                if len(event_date)!=7:raise RuntimeError("Permit month is not a daily date")
                try:dt.date.fromisoformat(event_date+"-01")
                except ValueError as error:raise RuntimeError("Bad permit month") from error
            else:
                if len(event_date)!=10:raise RuntimeError("Claimed exact date missing day")
                try:dt.date.fromisoformat(event_date)
                except ValueError as error:raise RuntimeError("Bad official date") from error
        if row.get("procurement_status") not in (
            "UNKNOWN","NOT_ESTABLISHED",
            "ORGANIZATION_TENDERS_PORTAL_EXISTS_NOT_PROJECT_SPECIFIC"):
            raise RuntimeError("This source evidence does not establish project-specific open procurement")
        if row.get("event_type") in DATED_EVENT_TYPES and event_date is None:
            raise RuntimeError("A claimed original dated notice is missing its date")
    for portal in document.get("procurement_portals",[]):
        if not _https(portal.get("url")):raise RuntimeError("Invalid procurement portal")
        if portal.get("project_specific_open_bid_verified") is not False:
            raise RuntimeError("Organizational portal is not a verified project bid")
    return True

def _summary(records):
    by_scope=defaultdict(list)
    by_site=defaultdict(set)
    for r in records:
        key=(r["city"].upper(),r["address"].upper(),r["exact_scope_id"].upper())
        by_scope[key].append(r)
        by_site[key[:2]].add(key[2])
    cases=[]
    for (city,address,scope),events in sorted(by_scope.items()):
        # This highest specificity gate applies only within exact ID.
        evidence_types={e["event_type"] for e in events}
        withdrawal="ENVIRONMENTAL_APPROVAL_WITHDRAWN" in evidence_types
        late="UNDER_CONSTRUCTION_PUBLIC_STATEMENT" in evidence_types
        if withdrawal:stage="SCOPE_WITHDRAWN_OR_CLOSED"
        elif late:stage="LATE_STAGE_CONSTRUCTION_UNDERWAY"
        elif "DEMOLITION_PERMIT_ISSUED" in evidence_types:
            stage="DEMOLITION_PERMIT_ALREADY_ISSUED"
        elif "COMPLETE_APPLICATION_PUBLIC_NOTICE" in evidence_types:
            stage="PUBLIC_COMPLETE_APPLICATION_BUYER_AND_VENDOR_UNKNOWN"
        elif "FORMAL_CONSULTATION_GIS" in evidence_types:
            stage="PREAPPLICATION_STAGE_CURRENTNESS_UNVERIFIED"
        elif "PROPERTY_LISTING_ACTIVE" in evidence_types:
            stage="COMMERCIAL_LEASING_NOT_CONSTRUCTION_PROCUREMENT"
        elif "HISTORICAL_APPROVAL" in evidence_types:
            stage="HISTORICAL_ENVIRONMENTAL_SITE_EVIDENCE_ONLY"
        else:stage="HISTORICAL_OR_CONTEXT_ONLY"
        first_date=next((e["event_date"] for e in events if
                         e["event_type"] in EARLY_EVENTS and
                         e.get("event_date") and len(e["event_date"])==10), "")
        first_basis=next((e["date_basis"] for e in events if
                    e["event_type"] in EARLY_EVENTS and
                    e.get("event_date") and len(e["event_date"])==10),"")
        other=sorted(by_site[(city,address)]-{scope})
        issues=[
           "Verify current responsible owner/operator and legal project applicant",
           "Prove project-specific work package exists and is open to suppliers",
           "Find public evidence for who actually makes purchasing decisions",
           "Confirm today's contract stage before external sales",
        ]
        if withdrawal:issues.insert(0,"This exact scope was WITHDRAWN: exclude until new separate application exists")
        if late:issues.insert(0,"Under construction: check only unawarded remaining packages")
        cases.append(dict(city=city,address=events[0]["address"],exact_scope_id=scope,
            scope_label=events[0].get("scope_label",""),actor=events[0].get("actor",""),
            actor_role=events[0].get("actor_role",""),
            stage_assessment=stage,project_specific_procurement="NOT_VERIFIED",
            original_public_date=first_date,event_date_basis=first_basis,
            issue_to_resolve="; ".join(issues),
            primary_evidence_url=events[0]["source_url"],
            relevant_source_count=len(events),
            distinct_other_scopes_same_site=len(other),
            same_site_other_scopes="; ".join(other),
            sale_ready="NO"))
    return cases

def _write(path,fields,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    with tmp.open("w",encoding="utf-8-sig",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)
    tmp.replace(path)

def run(source="research/hamilton_scope_stage_evidence_20261024.json",
        output_dir="GTA_RADAR_RESULTS"):
    data=json.loads(Path(source).read_text(encoding="utf-8"))
    validate(data)
    cases=_summary(data["checks"])
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    _write(output/"HAMILTON_EXACT_SCOPE_STAGE_AUDIT.csv",FIELDS,cases)
    _write(output/"HAMILTON_SCOPE_EVIDENCE_EVENTS.csv",EVENT_FIELDS,data["checks"])
    _write(output/"EARLY_OFFICIAL_PUBLIC_PROCUREMENT_CHANNELS.csv",PORTAL_FIELDS,
           data.get("procurement_portals",[]))
    checks=data["checks"]
    stats=[
        dict(metric="unique_exact_scope_ids",value=len(cases),
             meaning="Each agency application or project type is separate, even at same address"),
        dict(metric="public_evidence_checks",value=len(checks),
             meaning="Original sources corroborate specific statements, not procurement"),
        dict(metric="explicit_withdrawn_scopes",value=sum(x["stage_assessment"]==
             "SCOPE_WITHDRAWN_OR_CLOSED" for x in cases),
             meaning="Do not propagate withdrawal across unrelated site development"),
        dict(metric="existing_demolition_permit_scopes",value=sum(x["stage_assessment"]==
             "DEMOLITION_PERMIT_ALREADY_ISSUED" for x in cases),
             meaning="Demolition is not proof all future construction packages awarded"),
        dict(metric="verified_private_open_bid_packages",value=0,
             meaning="No scope-specific open private trade tender with current deadline confirmed"),
        dict(metric="qualified_sale_ready_leads",value=0,
             meaning="Buyer and available supplier work still require verification")]
    _write(output/"HAMILTON_SCOPE_STAGE_SUMMARY.csv",SCORE_FIELDS,stats)
    print("Hamilton evidence scopes",len(cases),"withdrawn",
          sum(x["stage_assessment"]=="SCOPE_WITHDRAWN_OR_CLOSED" for x in cases),
          "verified private open bids 0; no cross-site-status transfer")
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",default="research/hamilton_scope_stage_evidence_20261024.json")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args()
    raise SystemExit(run(a.source,a.output_dir))
