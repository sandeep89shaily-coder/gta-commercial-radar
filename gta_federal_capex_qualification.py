"""Conservative, offline qualification of Canadian industrial funding research records.

Consumes the existing federal candidate CSV. Outputs evidence-backed REVIEW queues,
never sales-ready leads. No external calls or new AI spend.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

SOURCE = "GTA_RADAR_FEDERAL_INDUSTRIAL_FUNDING_CANDIDATES.csv"
OUTPUT = "GTA_RADAR_FEDERAL_CAPEX_QUALIFIED_RESEARCH.csv"
TOP = "GTA_RADAR_FEDERAL_CAPEX_TOP20_RESEARCH.csv"
STATUS = "GTA_RADAR_FEDERAL_CAPEX_QUALIFICATION_STATUS.json"
HEADERS = ("research_rank","research_score","funding_record_id","recipient",
           "recipient_city_not_project_site","agreement_date_not_publication",
           "federal_funding_cad_not_equipment_budget","evidence_scope","equipment_categories_hypotheses",
           "specific_equipment_evidence","radar_company_match_status",
           "source_dataset","purchasing_status","buyer_verified","open_rfq_verified",
           "next_verification_action","research_only_status")
# Filter broad program language, grant-funded employment, college research equipment,
# ag subsidies, IT/software-only expenses and unrelated support programmes.
EXCLUDE = re.compile(
    r"\b(?:dairy farm investment program|research tools and instruments|"
    r"institute community support|canada summer jobs|csj 202[0-9]|"
    r"canexport smes|export market development|aid to publishers|"
    r"cultural spaces fund|student scholarships?|research fellowships?|"
    r"youth employment|training placement|trade show|"
    r"arts festival|language training|milking|livestock|"
    r"herd management|classroom equipment|camera equipment|"
    r"it equipment|laptop computers?)\b", re.I)
# Require an industrial production context AND a substantive acquisition,
# installation, modernization, manufacturing equipment or capacity signal.
INDUSTRY = re.compile(
    r"\b(?:manufactur(?:ing|e|er)|fabricat(?:ion|ing|e)|industrial|"
    r"production|processing|process line|machine shop|factory|"
    r"steel|metalwork|automotive|aerospace|packaging|assembly|"
    r"food processing|plant modernization|machining|welding)\b",re.I)
CAPEX = re.compile(
    r"\b(?:acquir(?:e|ing|ed|isition)|purchas(?:e|ing|ed)|procure(?:ment)?|"
    r"install(?:ation|ing|ed)?|new machinery|new equipment|"
    r"advanced (?:manufacturing )?equipment|production line|processing line|"
    r"manufacturing line|automated equipment|robotic welding|"
    r"cnc|automation|automated production|moderniz(?:ation|e)|"
    r"plant expansion|facility expansion|capacity expansion|"
    r"expand production|equipment upgrades?|equipment expansion|"
    r"manufacturing upgrade|capital equipment|production equipment)\b",re.I)
SPECIFIC = re.compile(
    r"\b(?:cnc|robotic welding|welding equipment|steel printing|"
    r"pressing (?:cell|equipment)|extrusion line|injection mould|"
    r"production line|packaging (?:line|equipment)|"
    r"processing (?:line|equipment)|automated beam|"
    r"laser cutting|machine tools?|bending equipment|"
    r"assembly line|automation equipment|manufacturing equipment|"
    r"advanced manufacturing equipment)\b",re.I)
CATS = [
    ("CNC and fabrication",re.compile(r"cnc|weld|bending|steel printing|laser cut|fabricat|machining",re.I)),
    ("Automation and robotics",re.compile(r"automati|robot|controls|assembly line",re.I)),
    ("Production and processing",re.compile(r"production line|processing|machinery|equipment|manufacturing",re.I)),
    ("Packaging",re.compile(r"packag",re.I)),
]
DATE = re.compile(r"^(20\d{2})(?:-(\d{2})-(\d{2}))?")
ORG = re.compile(r"\b(?:incorporated|inc|limited|ltd|corp|corporation|co)\b",re.I)


def norm(s):
    s=str(s or "").split("|",1)[0]
    s=ORG.sub(" ",s.casefold())
    return " ".join(re.sub(r"[^a-z0-9]+"," ",s).split())


def funding_date(s):
    m=DATE.match(str(s or ""))
    if not m:return None
    year=int(m.group(1))
    try:
        return dt.date(year,int(m.group(2) or 1),int(m.group(3) or 1))
    except ValueError:return None


def existing_names(root):
    names=set()
    sources=(
        (root/"GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv",("company",)),
        (root/"GTA_RADAR_COMBINED_31_CITY_PROJECT_MASTER.csv",("company","applicant_or_agent_source_claim","applicant")),
        (root/"GTA_RADAR_COLLECTION_MASTER.csv",("company","applicant","operator")),
    )
    found=[]
    for path,fields in sources:
        if not path.is_file() or path.is_symlink():continue
        found.append(str(path))
        with path.open(encoding="utf-8-sig",newline="") as f:
            for item in csv.DictReader(f):
                for name in fields:
                    value=norm(item.get(name,""))
                    if len(value)>=5:names.add(value)
    return names,found


def safe(value):
    t=str(value or "")
    return "'"+t if t.lstrip().startswith(("=","+","-","@")) else t


def run(results, *, input_csv=None, as_of=None, earliest_year=2025):
    root=Path(results)
    if not root.is_dir():
        raise FileNotFoundError("RESULTS_DIRECTORY_REQUIRED")
    source=Path(input_csv) if input_csv else root/SOURCE
    names, available=existing_names(root)
    today=as_of or dt.date.today()
    counters=Counter()
    qualified={}
    if source.is_file() and not source.is_symlink():
        with source.open(encoding="utf-8-sig",newline="") as f:
            reader=csv.DictReader(f)
            required={"funding_record_id","recipient","activity_excerpt",
                      "date_as_published","source_dataset"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError("UNRECOGNIZED_FEDERAL_CANDIDATES_SCHEMA")
            for item in reader:
                counters["input_rows"]+=1
                date=funding_date(item.get("date_as_published",""))
                if date is None or date.year<earliest_year or date>today:
                    counters["stale_undated_or_future"]+=1
                    continue
                name=item["recipient"].strip()
                description=" ".join((item.get("activity_excerpt") or "").split())
                title=" ".join((item.get("agreement_title") or "").split())
                scope=(title+" "+description).strip()
                if not name or not description or len(description)<25:
                    counters["insufficient_description"]+=1
                    continue
                if EXCLUDE.search(scope):
                    counters["unrelated_programme"]+=1
                    continue
                if not INDUSTRY.search(scope) or not CAPEX.search(scope):
                    counters["missing_industrial_capex_evidence"]+=1
                    continue
                specific=bool(SPECIFIC.search(scope))
                # avoid program boilerplate: require a concrete project statement,
                # not simply "support SMEs buying equipment".
                if re.search(r"\b(?:the program helps|intended to support|"
                             r"program is designed to|through the application of national)\b",
                             description,re.I):
                    counters["generic_program_boilerplate"]+=1
                    continue
                key=(norm(name),item["funding_record_id"].strip())
                if not key[0]:
                    counters["missing_name"]+=1
                    continue
                if key in qualified:
                    counters["duplicate_record"]+=1
                    continue
                cats=[cat for cat,rx in CATS if rx.search(scope)]
                score=50+(25 if specific else 0)+(10 if date.year==today.year else 0)
                score+=(5 if "automation" in scope.lower() or "robotic" in scope.lower() else 0)
                name_match="COMPANY_NAME_ONLY_REVIEW" if key[0] in names else (
                    "NO_MATCH_FOUND_IN_AVAILABLE_LOCAL_EXPORTS" if available else
                    "NOT_CHECKED_NO_LOCAL_RADAR_EXPORTS")
                qualified[key]={
                    "research_rank":"","research_score":str(score),
                    "funding_record_id":item["funding_record_id"],
                    "recipient":name.split("|",1)[0].strip(),
                    "recipient_city_not_project_site":item.get("recipient_city",""),
                    "agreement_date_not_publication":item.get("date_as_published",""),
                    "federal_funding_cad_not_equipment_budget":item.get("funding_value_cad_as_published",""),
                    "evidence_scope":description[:1200],
                    "equipment_categories_hypotheses":" | ".join(cats),
                    "specific_equipment_evidence":"YES_TEXT_MENTIONS_EQUIPMENT" if specific else "GENERAL_CAPEX_CONTEXT",
                    "radar_company_match_status":name_match,
                    "source_dataset":item.get("source_dataset",""),
                    "purchasing_status":"UNKNOWN_NOT_PROVEN_OPEN",
                    "buyer_verified":"False","open_rfq_verified":"False",
                    "next_verification_action":"Find exact plant site and original project announcement; verify equipment package, buyer and vendor-selection stage.",
                    "research_only_status":"RESEARCH_QUEUE_NOT_SALES_LEAD",
                }
    rows=sorted(qualified.values(),key=lambda x:(
        -int(x["research_score"]),x["agreement_date_not_publication"]*-1 if False else "",
        x["recipient"].casefold(),x["funding_record_id"]))
    # For equal scores, prefer recent funding dates; this date is not public posting.
    rows.sort(key=lambda x:(-int(x["research_score"]),
                            -(funding_date(x["agreement_date_not_publication"]).toordinal()),
                            x["recipient"].casefold(),x["funding_record_id"]))
    for index,row in enumerate(rows,1):
        row["research_rank"]=str(index)
    for output,items in ((OUTPUT,rows),(TOP,rows[:20])):
        with (root/output).open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=HEADERS)
            writer.writeheader()
            for row in items:writer.writerow({k:safe(row.get(k,"")) for k in HEADERS})
    report={
        "status":"RESEARCH_ONLY_NEEDS_PROCUREMENT_VERIFICATION" if source.is_file() else "NO_FEDERAL_CANDIDATES_INPUT",
        "input_rows":counters["input_rows"],"qualified_records":len(rows),
        "top20_records":min(20,len(rows)),"rejected_counts":dict(counters),
        "local_radar_exports_checked":available,
        "exact_projects_matched":0,
        "company_name_matches_only":sum(r["radar_company_match_status"]=="COMPANY_NAME_ONLY_REVIEW" for r in rows),
        "purchase_verified":0,"buyers_verified":0,"paid_ai_calls":0,
        "new_publication_dates_verified":0,"automatic_ai_investigations":0,
        "note":"Top20 is a research handoff, NOT verified leads or newly published projects. No outreach or model calls performed.",
        "qualified_csv":str(root/OUTPUT),"top20_csv":str(root/TOP),
    }
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--results",required=True)
    a.add_argument("--input-csv")
    a.add_argument("--earliest-year",type=int,default=2025)
    options=a.parse_args()
    if options.earliest_year<2020 or options.earliest_year>dt.date.today().year:
        a.error("Invalid earliest-year")
    print(json.dumps(run(options.results,input_csv=options.input_csv,
                         earliest_year=options.earliest_year),indent=2))


if __name__=="__main__":main()
