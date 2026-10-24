"""Hamilton industrial planning triage from live-pilot SQLite (no external AI).

Reuses published Hamilton GIS/notice snapshots. It does NOT prove today's
project status, supplier availability, buyers or exact filing dates. It only
groups matching file references; address-only overlaps remain REVIEW links.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path
from collections import defaultdict
from datetime import date
from early_cue_watch import _write_csv

FIELDS=("research_score","priority","site","address_key","source_gis_feature_id",
 "gis_file_number","gis_file_type","gis_file_year","municipal_description",
 "planning_stage_hypothesis","notice_file_number","notice_posted_date",
 "notice_record_url","notice_published_applicant","file_identity_match",
 "address_only_possible_links","distinct_gis_features_same_address",
 "potential_supplier_scopes","owner_operator_verified",
 "purchasing_contact_verified","vendor_selection_status","sale_readiness",
 "first_radar_observation","independent_stage_evidence","independent_stage_status",
 "related_company_at_site","related_company_role","related_company_source",
 "company_business_contact","next_research_action")
TRADE_PATTERNS={
 "INDUSTRIAL_FACILITY":r"\b(?:warehouse|distribution|manufactur|industrial|factory|employment)\b",
 "COLD_CHAIN":r"\b(?:cold storage|refrigerat|freezer|food processing)\b",
 "DATA_POWER":r"\b(?:data cent(?:er|re)|generator|substation|power)\b",
 "LOGISTICS":r"\b(?:loading dock|fulfilment|logistics)\b",
 "INFRASTRUCTURE":r"\b(?:sewage|stormwater|servicing|municipal road|road extension)\b",
 "HOSPITALITY":r"\b(?:hotel|retail|commercial)\b",
}
RESIDENTIAL=re.compile(r"\b(?:residential|dwellings?|apartments?|townhouses?|"
  r"condominiums?|housing)\b",re.I)
APP=re.compile(r"\b(?:FC|DPA|SUB|SPA|OPA|ZAC|ZBA)-\d{2,4}-\d{2,5}\b",re.I)
CIVIC=re.compile(r"(?<!\d)([1-9]\d{0,5}[A-Z]?)\s+"
    r"([A-Za-z0-9'-]+(?:\s+[A-Za-z0-9'-]+){0,5})\s+"
    r"(Road|Rd|Street|St|Drive|Dr|Avenue|Ave|Court|Ct|Crescent|Cres|"
    r"Boulevard|Blvd|Parkway|Pkwy|Way|Lane|Ln)\b",re.I)
STREETS={"ROAD":"RD","STREET":"ST","DRIVE":"DR","AVENUE":"AVE",
 "COURT":"CT","CRESCENT":"CRES","BOULEVARD":"BLVD","PARKWAY":"PKWY","LANE":"LN"}
def address_key(raw):
    raw=str(raw or "").strip()
    m=CIVIC.search(raw)
    if not m:return ""
    # Multi-civic parcels require reviewer, not implied merge.
    if re.search(r"\d+\s*(?:&|and|to|[-–])\s*\d+",raw,re.I):return ""
    street=" ".join((m.group(2),STREETS.get(m.group(3).upper(),m.group(3).upper())))
    return (m.group(1).upper()+" "+re.sub(r"\s+"," ",street.upper())).strip()

def file_key(raw):
    text=str(raw or "").upper().strip()
    m=APP.search(text)
    return m.group(0) if m else ""

def read_rows(database):
    path=Path(database)
    if not path.exists():
        raise FileNotFoundError("Hamilton pilot database absent; run the manual Hamilton watcher")
    db=sqlite3.connect("file:"+str(path.absolute())+"?mode=ro",uri=True)
    try:
        return [(src,rid,first,json.loads(body)) for src,rid,first,body in
               db.execute("SELECT source_id,record_id,first_seen_at,content FROM snapshots "
                          "WHERE source_id IN ('hamilton_applications_gis','hamilton_planning_notices')")]
    finally:db.close()

def evaluate(gis,notices,followups=None):
    """One row per GIS source feature, with explicit same-file evidence."""
    related_by_file=defaultdict(list)
    related_by_address=defaultdict(list)
    counts=defaultdict(int)
    for n in notices:
        key=file_key(n.get("file_number"))
        if key:related_by_file[key].append(n)
        site=address_key(n.get("site"))
        if site:related_by_address[site].append(n)
    for g in gis:
        key=address_key(g.get("site"))
        if key:counts[key]+=1
    evidence_by_file={file_key(r.get("file_number")):r for r in (followups or [])
                      if file_key(r.get("file_number"))}
    results=[]
    for g in gis:
        desc=g.get("description","") or ""
        site=g.get("site","") or ""
        key=address_key(site)
        gid=str(g.get("record_id") or "")
        filename=str(g.get("file_number") or "")
        fkey=file_key(filename)
        exact=related_by_file.get(fkey,[]) if fkey else []
        addr_only=related_by_address.get(key,[]) if key else []
        scope=[name for name,pattern in TRADE_PATTERNS.items()
               if re.search(pattern,desc,re.I)]
        if not scope and g.get("commercial_fit") not in (
            "POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"):
            continue
        year=int(g.get("source_application_year") or 0)
        if year<2024:continue
        residential=bool(RESIDENTIAL.search(desc))
        score=0
        if year>=2026:score+=18
        elif year==2025:score+=10
        else:score+=3
        if g.get("stage")=="FORMAL_CONSULTATION":score+=24
        if scope:score+=14+3*min(len(scope),3)
        if "COLD_CHAIN" in scope or "DATA_POWER" in scope:score+=12
        if "INFRASTRUCTURE" in scope:score+=4
        if exact:score+=20
        elif addr_only:score+=2
        if residential:score-=18
        if not key:score-=5
        notice=exact[0] if exact else {}
        supplier=";".join(scope)
        follow=evidence_by_file.get(fkey,{})
        later_stage=follow.get("stage","").startswith("UNDER_CONSTRUCTION")
        if later_stage:score=min(score,5)
        results.append(dict(
            research_score=score,
            priority=("REVIEW_LATE_STAGE" if later_stage else
                "RESEARCH_FIRST" if score>=60 else
                "RESEARCH_NEXT" if score>=35 else "LOW_PRIORITY"),
            site=site,address_key=key,source_gis_feature_id=gid,
            gis_file_number=filename,gis_file_type=g.get("title",""),
            gis_file_year=year,municipal_description=desc[:900],
            planning_stage_hypothesis=g.get("stage",""),
            notice_file_number=notice.get("file_number",""),
            notice_posted_date=notice.get("source_date",""),
            notice_record_url=notice.get("source_url",""),
            notice_published_applicant=notice.get("company",""),
            file_identity_match=("MATCHED_OFFICIAL_FILE_NUMBER_REVIEW" if exact
                                else "NOT_MATCHED_BY_FILE"),
            address_only_possible_links=";".join(sorted({n.get("source_url","")
                              for n in addr_only if n not in exact}))[:950],
            distinct_gis_features_same_address=counts.get(key,0),
            potential_supplier_scopes=supplier,
            owner_operator_verified="NO",
            purchasing_contact_verified="NO",
            vendor_selection_status="UNKNOWN",
            sale_readiness="NOT_SALE_READY",
            first_radar_observation=g.get("_first_seen_at",""),
            independent_stage_evidence=follow.get("stage_evidence_url",""),
            independent_stage_status=follow.get("stage","UNVERIFIED"),
            related_company_at_site=follow.get("related_organization",""),
            related_company_role=follow.get("org_relation",""),
            related_company_source=follow.get("organization_source",""),
            company_business_contact=follow.get("public_contact_route",""),
            next_research_action=(follow.get("next") or
               "Confirm project identity and current planning stage; "
               "identify operator/developer and public procurement route; "
               "verify whether work package is unawarded. "
               "Do not assume GIS FILE_YEAR is publication date.")))
    results.sort(key=lambda r:(-r["research_score"],
       -r["gis_file_year"],r["gis_file_number"]))
    return results

def run(database="data/early_hamilton_review.sqlite",
        output_dir="GTA_RADAR_RESULTS",limit=200,
        followup_file="research/hamilton_formal_consultation_followups_20261024.json"):
    if not 1<=limit<=1000:raise ValueError("limit 1..1000")
    rows=read_rows(database)
    gis=[];notices=[]
    for sid,rid,first,row in rows:
        row["_first_seen_at"]=first
        if sid=="hamilton_applications_gis":gis.append(row)
        else:notices.append(row)
    f=Path(followup_file) if followup_file else None
    followups=json.loads(f.read_text(encoding="utf-8")).get("records",[]) if f and f.exists() else []
    queue=evaluate(gis,notices,followups)
    folder=Path(output_dir);folder.mkdir(parents=True,exist_ok=True)
    _write_csv(folder/"HAMILTON_INDUSTRIAL_TRIAGE_REVIEW.csv",FIELDS,queue[:limit])
    print("Hamilton GIS",len(gis),"notice sources",len(notices),
          "possible significant files",len(queue),"export",min(len(queue),limit))
    print("Research-only; procurement/buyer unverified; all initial GIS features historical")
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database",default="data/early_hamilton_review.sqlite")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    p.add_argument("--limit",type=int,default=200)
    p.add_argument("--followup-file",default="research/hamilton_formal_consultation_followups_20261024.json")
    a=p.parse_args()
    raise SystemExit(run(a.database,a.output_dir,a.limit,a.followup_file))
