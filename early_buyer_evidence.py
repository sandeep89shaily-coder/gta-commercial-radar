"""Evidence workbench for GTA Radar. Never silently marks a project sales-ready.

Inputs: EARLY_EVIDENCE_ACTIONABILITY_GATES.csv produced by independent pilot
watchers, optional prior human worksheet, never V8 or DeepSeek.

Reviewer entries survive every refresh. This code checks formal evidence
completeness, NOT authenticity of links or proof that a purchasing officer
exists. 'ASSEMBLED_FOR_HUMAN_REVIEW' is not a verified customer lead.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import re
from pathlib import Path
from urllib.parse import urlparse

WORKSHEET_FIELDS=(
    "source_id","item_id","city","site","title","original_record_url",
    "first_seen_at","source_posted_date","published_entity_role_unverified",
    "reviewer","reviewed_on","project_identity_confirmed","identity_evidence_url",
    "buyer_organization","buyer_relationship","buyer_role_evidence_url",
    "specific_work_package","work_package_evidence_url",
    "public_business_contact","public_contact_evidence_url",
    "procurement_state","procurement_state_evidence_url",
    "other_buyer_selected","other_buyer_selected_evidence_url",
    "stage_current_evidence_url","confidence_notes","reviewer_signoff",
    "supplier_category","outreach_status","feedback","quality_status")
OUTPUT_FIELDS=("source_id","item_id","city","site","buyer_organization",
    "specific_work_package","public_business_contact","supplier_category",
    "procurement_state","quality_status","missing_evidence",
    "source_url","buyer_role_evidence_url","procurement_state_evidence_url")
REVIEW_FIELDS=("metric","value","interpretation")
ALLOWED_PROCUREMENT={
 "UNKNOWN","OPEN_CONFIRMED","NOT_SELECTED_CONFIRMED",
 "SELECTED_CONFIRMED","CLOSED_CONFIRMED","NOT_APPLICABLE"}
ALLOWED_RELATIONSHIPS={"UNKNOWN","OWNER","DEVELOPER","OPERATOR",
                       "TENANT","GENERAL_CONTRACTOR","PUBLIC_BUYER"}
NO_VALUES={"","UNKNOWN","UNVERIFIED","NOT_FOUND","N/A","NONE"}
TERMS=("source_id","item_id")

def official_url(value):
    value=str(value or "").strip()
    p=urlparse(value)
    return bool(p.scheme=="https" and p.hostname and
      "." in p.hostname and not p.username and not p.password and
      len(value)<=1300 and not p.hostname.endswith((".local",".internal",".invalid")))

def iso(value,today):
    try:
        d=dt.date.fromisoformat(str(value or ""))
        return bool(dt.date(2020,1,1)<=d<=today)
    except (ValueError,TypeError):return False

def read(path):
    file=Path(path)
    if not file.is_file():return []
    with file.open("r",encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))

def write(path,fields,records):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    with temp.open("w",encoding="utf-8-sig",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=fields,extrasaction="ignore")
        writer.writeheader();writer.writerows(records)
    temp.replace(path)

def make_item(source):
    return dict(
        source_id=source.get("source_id",""),
        item_id=source.get("item_id",""),
        city=source.get("city",""),site=source.get("site",""),
        title=source.get("title",""),
        original_record_url=source.get("record_url",""),
        first_seen_at=source.get("radar_first_seen",""),
        source_posted_date=source.get("official_public_posting_date",""),
        published_entity_role_unverified=source.get("published_entity",""),
        reviewer="",reviewed_on="",
        project_identity_confirmed="NO",identity_evidence_url="",
        buyer_organization="",buyer_relationship="UNKNOWN",
        buyer_role_evidence_url="",
        specific_work_package="",work_package_evidence_url="",
        public_business_contact="",public_contact_evidence_url="",
        procurement_state="UNKNOWN",procurement_state_evidence_url="",
        other_buyer_selected="UNKNOWN",other_buyer_selected_evidence_url="",
        stage_current_evidence_url="",confidence_notes="",reviewer_signoff="NO",
        supplier_category="",outreach_status="NOT_CONTACTED",feedback="",
        quality_status="UNREVIEWED")

def review(row,today=None):
    today=today or dt.datetime.now(dt.timezone.utc).date()
    missing=[]
    if row.get("project_identity_confirmed","").strip().upper()!="YES":
        missing.append("project_identity_not_reviewed")
    if not official_url(row.get("original_record_url")):
        missing.append("original_source_missing")
    if not official_url(row.get("identity_evidence_url")):
        missing.append("identity_evidence_missing")
    if row.get("buyer_organization","").strip().upper() in NO_VALUES:
        missing.append("buyer_organization_unverified")
    if row.get("buyer_relationship","").strip().upper() not in ALLOWED_RELATIONSHIPS-{"UNKNOWN"}:
        missing.append("buying_role_unverified")
    if not official_url(row.get("buyer_role_evidence_url")):
        missing.append("buyer_role_source_missing")
    if row.get("specific_work_package","").strip().upper() in NO_VALUES:
        missing.append("work_package_unverified")
    if not official_url(row.get("work_package_evidence_url")):
        missing.append("work_package_source_missing")
    if row.get("public_business_contact","").strip().upper() in NO_VALUES:
        missing.append("business_contact_missing")
    if not official_url(row.get("public_contact_evidence_url")):
        missing.append("business_contact_source_missing")
    if row.get("supplier_category","").strip().upper() in NO_VALUES:
        missing.append("supplier_category_missing")
    state=row.get("procurement_state","").strip().upper()
    if state not in ALLOWED_PROCUREMENT or state=="UNKNOWN":
        missing.append("procurement_status_unverified")
    if not official_url(row.get("procurement_state_evidence_url")):
        missing.append("procurement_source_missing")
    if not official_url(row.get("stage_current_evidence_url")):
        missing.append("current_stage_source_missing")
    if not iso(row.get("reviewed_on"),today):
        missing.append("dated_reviewer_check_missing")
    if not row.get("reviewer","").strip():
        missing.append("reviewer_missing")
    if row.get("reviewer_signoff","").strip().upper()!="YES":
        missing.append("human_signoff_missing")
    source_urls=[row.get("identity_evidence_url",""),
          row.get("buyer_role_evidence_url",""),
          row.get("procurement_state_evidence_url","")]
    if len({str(x).strip() for x in source_urls if official_url(x)})<2:
        missing.append("independent_sources_insufficient")
    if state in {"CLOSED_CONFIRMED","SELECTED_CONFIRMED","NOT_APPLICABLE"}:
        return "NOT_OPEN_FOR_SALE_REVIEW","confirmed_closed_or_already_selected"
    if missing:
        return "INCOMPLETE_EVIDENCE",";".join(missing)
    # Even these checks cannot authenticate source documents or who purchases.
    return "ASSEMBLED_FOR_HUMAN_REVIEW_NOT_VERIFIED_LEAD","formal_fields_complete_validate_links_roles_and_open_work"

def merge(prior,current):
    """Do not overwrite human evidence on a later run. Indexed project title,
    municipality and URL are refreshed only when the reviewer has no notes."""
    previous={(r.get("source_id",""),r.get("item_id","")):r for r in prior}
    merged=[]
    already=set()
    for source in current:
        key=(source.get("source_id",""),source.get("item_id",""))
        if not all(key) or key in already:continue
        already.add(key)
        row=make_item(source)
        if key in previous:
            # Preserve all previously written human columns, including dates,
            # and project identity if a source disappears from live results.
            old=previous[key]
            human=WORKSHEET_FIELDS[9:-1]
            for field in human:
                row[field]=old.get(field,row.get(field,""))
        merged.append(row)
    # Retain human work for projects no longer in the source. Its original
    # presence is historical, not proof the site is still active.
    for key,old in previous.items():
        if key not in already:
            retained={field:old.get(field,"") for field in WORKSHEET_FIELDS}
            retained["confidence_notes"]=(retained["confidence_notes"]+
              " | NO_LONGER_IN_CURRENT_RESEARCH_QUEUE;CHECK_PROJECT_CURRENT_STATUS").strip(" |")
            merged.append(retained)
    return merged

def run(input_csv="GTA_RADAR_RESULTS/EARLY_EVIDENCE_ACTIONABILITY_GATES.csv",
        output_dir="GTA_RADAR_RESULTS",today=None):
    today=today or dt.datetime.now(dt.timezone.utc).date()
    output=Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    incoming=read(input_csv)
    path=output/"EARLY_BUYER_EVIDENCE_WORKSHEET.csv"
    if not Path(input_csv).is_file():
        print("No evidence input yet. Run existing early cue pilot and cross-match first.")
        return 1
    merged=merge(read(path),incoming)
    report=[]
    for row in merged:
        quality,reason=review(row,today=today)
        row["quality_status"]=quality
        report.append(dict(source_id=row["source_id"],item_id=row["item_id"],
            city=row["city"],site=row["site"],
            buyer_organization=row["buyer_organization"],
            specific_work_package=row["specific_work_package"],
            public_business_contact=row["public_business_contact"],
            supplier_category=row["supplier_category"],
            procurement_state=row["procurement_state"],
            quality_status=quality,missing_evidence=reason,
            source_url=row["original_record_url"],
            buyer_role_evidence_url=row["buyer_role_evidence_url"],
            procurement_state_evidence_url=row["procurement_state_evidence_url"]))
    write(path,WORKSHEET_FIELDS,merged)
    write(output/"EARLY_BUYER_EVIDENCE_GATE_AUDIT.csv",OUTPUT_FIELDS,report)
    ready=sum(row["quality_status"]=="ASSEMBLED_FOR_HUMAN_REVIEW_NOT_VERIFIED_LEAD"
              for row in report)
    counts=[
     dict(metric="research_rows",value=len(merged),
          interpretation="Planning records and public cues; not unique confirmed buyer projects"),
     dict(metric="human_evidence_assembled",value=ready,
          interpretation="Formal fields present, but URLs and claims not independently authenticated by code"),
     dict(metric="verified_sale_ready_opportunities",value=0,
          interpretation="Requires manual independent confirmation, not possible from worksheet alone"),
     dict(metric="target_opportunities",value=10,
          interpretation="Project goal, not a measured result"),
     dict(metric="paying_pilot_customers",value="NOT_MEASURED",
          interpretation="No billing/CRM system connected; payment cannot be inferred") ]
    write(output/"EARLY_BUSINESS_MILESTONES.csv",REVIEW_FIELDS,counts)
    print("Buyer evidence rows:",len(merged),
          "assembled for human review:",ready,
          "verified automatically: 0 | no paid APIs")
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",default="GTA_RADAR_RESULTS/EARLY_EVIDENCE_ACTIONABILITY_GATES.csv")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    args=p.parse_args()
    raise SystemExit(run(args.input,args.output_dir))
