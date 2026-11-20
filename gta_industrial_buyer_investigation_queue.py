"""Join existing federal, ERO, and commercial evidence into an industrial
company-investigation handoff. Never invent a project, buyer or open RFQ.

This is an offline input for the existing company-contact investigation workflow;
it does not trigger paid searches on unverified federal grant descriptions.
"""
import csv
import json
import re
from pathlib import Path

FEDERAL = "GTA_RADAR_FEDERAL_CAPEX_TOP20_RESEARCH.csv"
COMMERCIAL = "GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv"
MASTER = "GTA_RADAR_COMBINED_31_CITY_PROJECT_MASTER.csv"
OUTPUT = "GTA_RADAR_INDUSTRIAL_BUYER_INVESTIGATION_QUEUE.csv"
STATUS = "GTA_RADAR_INDUSTRIAL_BUYER_INVESTIGATION_STATUS.json"
HEADERS = ("research_rank","company","funding_record_id","funding_agreement_date_not_publication",
           "recipient_city_not_verified_site","equipment_scope_from_funding",
           "equipment_category_hypothesis","potential_existing_company_name_match",
           "possible_municipal_application_id_not_project_verified",
           "corroborating_source_type","corroborating_source_url",
           "buyer_verified","procurement_open_verified","research_state",
           "next_verification_action")
ORG = re.compile(r"\b(?:incorporated|inc|limited|ltd|corp|corporation|co)\b",re.I)

def normal(s):
    return " ".join(re.sub(r"[^a-z0-9]"," ",ORG.sub(" ",str(s or "").casefold())).split())

def rows(path):
    if not path.is_file() or path.is_symlink(): return []
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def clean(value):
    s=str(value or "")
    return "'"+s if s.lstrip().startswith(("=","+","-","@")) else s

def run(results):
    root=Path(results)
    if not root.is_dir():raise FileNotFoundError("RESULTS_DIRECTORY_REQUIRED")
    federal=rows(root/FEDERAL)
    commercial=rows(root/COMMERCIAL)
    master=rows(root/MASTER)
    # Exact normalized company names are weak hints, never verified project links.
    grouped={}
    for r in commercial:
        key=normal(r.get("company"))
        if key:
            grouped.setdefault(key,[]).append(r)
    identified={}
    for r in master:
        key=normal(r.get("applicant_or_agent_source_claim") or r.get("company"))
        if key:
            identified.setdefault(key,[]).append(r)
    out=[]
    for f in federal:
        company=(f.get("recipient") or "").strip()
        if not company:continue
        key=normal(company)
        related=grouped.get(key,[])
        municipal=identified.get(key,[])
        match=related[0] if related else {}
        project=municipal[0] if municipal else {}
        out.append({
            "research_rank":f.get("research_rank",""),
            "company":company,"funding_record_id":f.get("funding_record_id",""),
            "funding_agreement_date_not_publication":f.get("agreement_date_not_publication",""),
            "recipient_city_not_verified_site":f.get("recipient_city_not_project_site",""),
            "equipment_scope_from_funding":f.get("evidence_scope",""),
            "equipment_category_hypothesis":f.get("equipment_categories_hypotheses",""),
            "potential_existing_company_name_match":"REVIEW_ONLY" if match or project else "NONE_IN_AVAILABLE_EXPORTS",
            "possible_municipal_application_id_not_project_verified":project.get("application_id",""),
            "corroborating_source_type":match.get("source_type",""),
            "corroborating_source_url":match.get("source_url",""),
            "buyer_verified":"False","procurement_open_verified":"False",
            "research_state":"PROJECT_SPECIFIC_BUYER_RESEARCH_NOT_YET_DONE",
            "next_verification_action":(
                "Find a recent company or government announcement identifying the exact project plant; "
                "confirm any equipment packages remain prospective; obtain project engineering/procurement "
                "business contact with a cited project-specific relationship."),
        })
    with (root/OUTPUT).open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=HEADERS);writer.writeheader()
        writer.writerows([{k:clean(r[k]) for k in HEADERS} for r in out])
    report={"status":"FEDERAL_TO_COMPANY_INVESTIGATION_RESEARCH_ONLY",
            "federal_top20_input_rows":len(federal),"investigation_queue_rows":len(out),
            "existing_company_name_matches_only":sum(x["potential_existing_company_name_match"]=="REVIEW_ONLY" for x in out),
            "exact_project_matches_verified":0,"verified_project_buyers":0,
            "verified_open_equipment_orders":0,"paid_model_calls":0,
            "paid_company_investigations_started":0,
            "warning":"Company matching is only a review hint. A funding award is not an RFQ. Further company/plant and procurement verification required.",
            "output_csv":str(root/OUTPUT)}
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
