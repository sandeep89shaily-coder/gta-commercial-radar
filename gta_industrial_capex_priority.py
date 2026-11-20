"""Focused industrial capex and equipment procurement research triage.

Consumes the existing offline equipment index; no network, AI, invented buyers
or automatic commercial releases. Evidence claims and inferred trade fit stay
separate. Output is a prioritized human investigation queue.
"""
from __future__ import annotations
import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

INPUT = "GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv"
OUTPUT = "GTA_RADAR_INDUSTRIAL_CAPEX_PRIORITY_QUEUE.csv"
STATUS = "GTA_RADAR_INDUSTRIAL_CAPEX_PRIORITY_STATUS.json"
FIELDS = ("priority","source_type","company","municipality","physical_project_address_unverified",
          "direct_equipment_evidence","potential_supplier_categories_not_verified",
          "evidence_stage","purchase_stage","buyer_status","confidence",
          "source_url","source_date","source_date_basis","next_research_action",
          "reason_for_hold")
FAMILIES = (
    ("Process machinery",r"production line|processing line|pressing cell|machinery|manufactur(?:ing)? plant|production equipment"),
    ("Automation and robotics",r"automation|automated|robot(?:ic)?|conveyor|controls|assembly line"),
    ("Fabrication equipment",r"cnc|bending equipment|steel printing|laser cutting|cutting system|welding|press brake"),
    ("Industrial HVAC and process cooling",r"chiller|cooling tower|industrial refrigeration|dust collect|scrubber|ventilat|air handling"),
    ("Power and electrical",r"data cent(?:er|re)|transformer|switchgear|substation|electrical"),
    ("Water and process treatment",r"wastewater|effluent|water treatment|filtration"),
)
RX=[(name,re.compile(pattern,re.I)) for name,pattern in FAMILIES]
EXPLICIT=re.compile(r"\b(?:acquir(?:e|ing|ed)|purchas(?:e|ing|ed)|install(?:ation|ing|ed)?|"
                    r"replace(?:ment|d)?|new|expand(?:sion|ing)?|moderniz(?:e|ation)|"
                    r"upgrade|automated)\b",re.I)
SITE_ONLY=re.compile(r"\b(?:data cent(?:er|re)|new plant|manufactur(?:ing)? plant|factory)\b",re.I)
NEGATIVE=re.compile(r"\b(?:completed|commissioned|fully operational|already awarded|contract awarded)\b",re.I)
RESIDENTIAL=re.compile(r"\b(?:residential subdivision|single.detached|townhouse|condominium|apartments?)\b",re.I)


def read_csv(path):
    if not path.is_file() or path.is_symlink():
        return []
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def url_ok(value):
    # Multiple legitimate source URLs may occur in the upstream index.
    urls = re.findall(r"https://[^\s|;,]+",value or "")
    return bool(urls) and all(urlsplit(url).hostname for url in urls)


def run(root):
    root=Path(root)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_REQUIRED")
    entries=read_csv(root/INPUT)
    chosen={}
    rejected=Counter()
    for item in entries:
        source=(item.get("source_url") or "").strip()
        company=(item.get("company") or "").strip()
        city=(item.get("municipality") or "").strip()
        scope=(item.get("equipment_or_scope") or "").strip()
        if not source or not url_ok(source) or not company or not scope:
            rejected["MISSING_TRACEABLE_COMPANY_SCOPE_OR_SOURCE"]+=1
            continue
        if RESIDENTIAL.search(scope) and not SITE_ONLY.search(scope):
            rejected["RESIDENTIAL_NOT_INDUSTRIAL_CAPEX"]+=1
            continue
        matched=[name for name,rx in RX if rx.search(scope)]
        if not matched:
            rejected["NO_SUPPORTED_INDUSTRIAL_CAPEX_FIT"]+=1
            continue
        is_specific=bool(EXPLICIT.search(scope)) and not (SITE_ONLY.search(scope) and not
                     re.search(r"\b(?:equipment|line|machine|automation|install|replace|cnc|pressing)\b",scope,re.I))
        # An announcement of a facility is not an equipment RFQ.
        evidence="SPECIFIC_EQUIPMENT_ACTION_IN_SOURCE_SCOPE" if is_specific else "FACILITY_OR_PROCESS_SCOPE_ONLY"
        negative=bool(NEGATIVE.search(scope))
        contact=(item.get("contact_name_verified") or "").strip()
        role=(item.get("contact_professional_title") or "").strip()
        buyer=item.get("purchasing_authority_verified","").lower()=="true"
        # The upstream index forces False, never infer named purchaser from a title.
        buyer_status="INDEPENDENT_PURCHASER_VERIFICATION_REQUIRED"
        if negative:
            buying="PAST_OR_AWARDED_RECHECK"
        else:
            buying="UNKNOWN_NOT_A_LIVE_RFQ"
        score=40+(20 if is_specific else 0)+(5 if city else 0)+(5 if contact and role else 0)
        if negative:
            score-=25
        if item.get("source_type")=="ERO_INSTRUMENT_PROPOSAL":
            score-=5
        next_action=("Confirm whether any equipment procurement remains prospective, the project operator, "
                     "capital-project owner, engineering/maintenance lead, vendor selection stage and purchasing contact.")
        if not is_specific:
            next_action=("Identify actual equipment packages from project drawings or company disclosures before supplier outreach; "
                         "then confirm operator, project owner and procurement status.")
        row={"priority":str(max(0,score)),
             "source_type":item.get("source_type",""),"company":company,"municipality":city,
             "physical_project_address_unverified":item.get("physical_project_address_unverified",""),
             "direct_equipment_evidence":scope,
             "potential_supplier_categories_not_verified":" | ".join(matched),
             "evidence_stage":evidence,"purchase_stage":buying,
             "buyer_status":buyer_status,"confidence":"RESEARCH_ONLY_NOT_BUYER_VERIFIED",
             "source_url":source,"source_date":item.get("source_date",""),
             "source_date_basis":item.get("source_date_basis",""),
             "next_research_action":next_action,
             "reason_for_hold":"NO_VERIFIED_PURCHASER_OR_OPEN_RFQ"}
        key=(company.casefold(),city.casefold(),source.casefold(),scope.casefold())
        chosen.setdefault(key,row)
    rows=sorted(chosen.values(),key=lambda r:(-int(r["priority"]),r["company"].casefold(),r["source_url"]))
    with (root/OUTPUT).open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:("'"+str(row[k]) if str(row[k]).lstrip().startswith(("=","+","-","@")) else row[k])
                             for k in FIELDS})
    report={"status":"INDUSTRIAL_CAPEX_RESEARCH_QUEUE_ONLY",
            "input_rows":len(entries),"qualified_industrial_research_candidates":len(rows),
            "specific_equipment_action_candidates":sum(r["evidence_stage"]=="SPECIFIC_EQUIPMENT_ACTION_IN_SOURCE_SCOPE" for r in rows),
            "facility_only_candidates":sum(r["evidence_stage"]=="FACILITY_OR_PROCESS_SCOPE_ONLY" for r in rows),
            "rejected":dict(rejected),"verified_purchasers":0,"verified_open_rfqs":0,
            "additional_http_requests":0,"additional_paid_ai_calls":0,
            "note":"Keyword detection and scores are triage aids, not verified equipment specifications or buying intent.",
            "output_csv":str(root/OUTPUT)}
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
