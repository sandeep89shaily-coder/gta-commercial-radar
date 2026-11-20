"""Stream an operator-supplied official Canada grants CSV into Radar industrial research.

No network calls, no licence bypass, no customer leads, no claim of purchase intent.
Full federal snapshot is multi-GB: process one CSV row at a time.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SOURCE_DIR = "OFFICIAL_FEDERAL_GRANTS"
SOURCE_FILE = "grants.csv"
OUTPUT = "GTA_RADAR_FEDERAL_INDUSTRIAL_FUNDING_CANDIDATES.csv"
STATUS = "GTA_RADAR_FEDERAL_INDUSTRIAL_FUNDING_STATUS.json"
OFFICIAL = "https://open.canada.ca/data/en/dataset/432527ab-7aac-45b5-81d6-7597107a7013"
COLS = ("funding_record_id","recipient","recipient_city","recipient_province",
        "funding_value_cad_as_published","agreement_title","activity_excerpt",
        "date_as_published","date_type","capital_signal",
        "known_company_match_only","source_dataset","review_state","buyer_verified",
        "open_supplier_package_verified")
FIELDS = {
    "recipient": ("recipient_legal_name","recipient_operating_name","recipient_name"),
    "city": ("recipient_city",),
    "province": ("recipient_province",),
    "title": ("agreement_title_en","agreement_title","project_title_en"),
    "description": ("description_en","expected_results_en","description","expected_results"),
    "value": ("agreement_value","federal_contribution","total_agreement_value"),
    "date": ("agreement_start_date","agreement_date","agreement_signed_date","fiscal_year"),
    "record": ("reference_number","agreement_number","ref_number","id"),
}
INDUSTRIAL = re.compile(
    r"\b(?:manufactur(?:ing|er|e)|production|factory|industrial|processing|"
    r"fabrication|metalworking|transformer|semiconductor|automotive|aerospace|"
    r"packaging|food processing|machinery|equipment|plant)\b",re.I)
CAPITAL = re.compile(
    r"\b(?:machinery|equipment|capital investment|production line|processing line|"
    r"manufacturing line|assembly line|automati(?:on|c|ng)|robotics?|robotic|"
    r"fabrication|bending|pressing|industrial expansion|expand production|"
    r"plant expansion|facility expansion|facility upgrade|moderniz(?:ation|e)|"
    r"retrofit|commissioning|install(?:ation|ing)?)\b",re.I)
EXCLUDE = re.compile(r"\b(?:student scholarships?|research fellowships?|"
                     r"tourism marketing|arts festival|language training)\b",re.I)
ON = {"ON","ONTARIO"}

def field(row, names):
    return next((str(row[n]).strip() for n in names
                 if n in row and row[n] not in (None,"")), "")

def norm(s):
    s=re.sub(r"[^a-z0-9 ]"," ",str(s).casefold())
    s=re.sub(r"\b(?:incorporated|inc|limited|ltd|corp|corporation)\b"," ",s)
    return " ".join(s.split())

def match_names(root):
    names=set()
    for path in (root/"GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv",
                 root/"GTA_RADAR_COMBINED_31_CITY_PROJECT_MASTER.csv"):
        if not path.is_file():continue
        with path.open(encoding="utf-8-sig",newline="") as fp:
            for row in csv.DictReader(fp):
                for column in ("company","applicant_or_agent_source_claim"):
                    n=norm(row.get(column,""))
                    if len(n)>=6:names.add(n)
    return names

def run(results, *, input_csv=None, max_output=5000):
    root=Path(results)
    root.mkdir(parents=True,exist_ok=True)
    source=Path(input_csv) if input_csv else root/SOURCE_DIR/SOURCE_FILE
    count=Counter(); kept={}; known=match_names(root)
    state="NO_LOCAL_OFFICIAL_SNAPSHOT"
    if source.is_file() and not source.is_symlink():
        state="COMPLETE_STREAMING_OFFICIAL_SNAPSHOT"
        with source.open(encoding="utf-8-sig",newline="",errors="replace") as fp:
            reader=csv.DictReader(fp)
            if not reader.fieldnames:
                raise ValueError("EMPTY_FEDERAL_GRANTS_HEADER")
            mandatory=("recipient","city","province","description")
            missing=[k for k in mandatory if not any(n in reader.fieldnames for n in FIELDS[k])]
            if missing:raise ValueError("UNRECOGNIZED_GRANTS_SCHEMA:"+",".join(missing))
            for item in reader:
                count["input_rows"]+=1
                if field(item,FIELDS["province"]).upper() not in ON:
                    continue
                count["ontario_rows"]+=1
                company=field(item,FIELDS["recipient"])
                city=field(item,FIELDS["city"])
                title=field(item,FIELDS["title"])
                desc=field(item,FIELDS["description"])
                if not company or not city or not desc:
                    count["missing_project_context"]+=1
                    continue
                details=(title+" "+desc)[:12000]
                if EXCLUDE.search(details) or not INDUSTRIAL.search(details) or not CAPITAL.search(details):
                    count["not_explicit_industrial_capex"]+=1
                    continue
                count["matching_rows"]+=1
                rec=field(item,FIELDS["record"])
                if not rec:
                    rec=hashlib.sha256((company+"|"+city+"|"+title+"|"+
                        field(item,FIELDS["date"])).encode()).hexdigest()[:20]
                key=(norm(company),rec)
                if key in kept:
                    count["duplicate_record"]+=1
                    continue
                if len(kept)>=max_output:
                    count["over_output_limit"]+=1
                    continue
                company_norm=norm(company)
                kept[key]={
                  "funding_record_id":rec,"recipient":company,"recipient_city":city,
                  "recipient_province":"Ontario",
                  "funding_value_cad_as_published":field(item,FIELDS["value"]),
                  "agreement_title":title,
                  "activity_excerpt":desc[:1200],
                  "date_as_published":field(item,FIELDS["date"]),
                  "date_type":"FUNDING_AGREEMENT_OR_FISCAL_YEAR_NOT_PROJECT_ANNOUNCEMENT",
                  "capital_signal":"SOURCE_DESCRIPTION_INDUSTRIAL_CAPEX_KEYWORDS_REVIEW_REQUIRED",
                  "known_company_match_only":str(company_norm in known),
                  "source_dataset":OFFICIAL,
                  "review_state":"RESEARCH_ONLY_VERIFY_PROJECT_SITE_EQUIPMENT_AND_TIMING",
                  "buyer_verified":"False","open_supplier_package_verified":"False",
                }
    out=root/OUTPUT
    with out.open("w",newline="",encoding="utf-8-sig") as fp:
        writer=csv.DictWriter(fp,fieldnames=COLS)
        writer.writeheader()
        for row in kept.values():
            writer.writerow({k:("'"+str(v) if str(v).lstrip().startswith(("=","+","-","@")) else v)
                             for k,v in row.items()})
    report={"status":state,"input_path":str(source),
            "input_rows":count["input_rows"],"ontario_rows":count["ontario_rows"],
            "industrial_capex_candidates":len(kept),
            "already_present_company_name_matches":sum(x["known_company_match_only"]=="True" for x in kept.values()),
            "rejected_or_overflow":dict(count),
            "paid_ai_calls":0,"web_requests":0,"customer_ready_leads":0,
            "warning":"Recipient city is not a verified project site; funding is not equipment spending, a new announcement, an open RFQ or purchasing intent. Local snapshot is operator-supplied. Company-name equality is not an exact project match.",
            "source_catalogue_url":OFFICIAL,"output_csv":str(out)}
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    p.add_argument("--input-csv")
    p.add_argument("--max-output",type=int,default=5000)
    a=p.parse_args()
    if a.max_output<1 or a.max_output>50000:raise SystemExit("max-output range 1..50000")
    print(json.dumps(run(a.results,input_csv=a.input_csv,max_output=a.max_output),indent=2))

if __name__=="__main__":main()
