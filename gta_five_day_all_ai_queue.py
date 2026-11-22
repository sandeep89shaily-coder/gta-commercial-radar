"""Create an uncapped, source-backed DeepSeek investigation queue from fresh Radar.

The freshness-first ALL exports are research candidate sets, never verified
open contracts. Only rows with source date within five calendar days, meaningful
scope and a usable HTTPS original-source URL are eligible for paid search/fetch/
analysis. Every candidate remains in the ALL exports even when AI is held.
No network, provider calls, emails, address guessing, or customer releases here.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from gta_freshness import _date
from gta_freshness_first_daily_selection import GENERAL_ALL, EQUIPMENT_ALL
from candidate_scoring import score, MIN_SELECTION_SCORE

AI_INPUT = "GTA_RADAR_FIVE_DAY_ALL_AI_CANDIDATES.csv"
AUDIT = "GTA_RADAR_FIVE_DAY_ALL_AI_CANDIDATE_AUDIT.csv"
STATUS = "GTA_RADAR_FIVE_DAY_ALL_AI_QUEUE_STATUS.json"
FIELDS = ("project_id", "city", "address", "description", "source_id",
          "source_keys", "record_source_url", "current_source_status",
          "source_record_date", "source_date_basis", "company_name",
          "lane", "freshness_class", "observation", "ai_research_priority")
AUDIT_FIELDS = FIELDS + ("qualification", "reason", "score", "score_tier")
HOLD_STAGE = re.compile(
    r"\\b(?:completed|operational|already awarded|supplier selected|"
    r"installation completed|cancelled|canceled|withdrawn|closed)\\b", re.I)
CONCRETE_SCOPE = re.compile(
    r"\\b(?:manufactur\\w*|industrial|warehouse|commercial|office|"
    r"restaurant|retail|construction|renovat\\w*|fit.out|expan\\w*|"
    r"machin\\w*|automation|equipment|factory|plant|robot\\w*|"
    r"processing|stamping|production|install\\w*|distribution)\\b", re.I)

def _read(path):
    if not path.is_file():
        return []
    if path.is_symlink() or path.stat().st_size > 50_000_000:
        raise ValueError("UNSAFE_FIVE_DAY_AI_INPUT")
    with path.open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))

def _url(value):
    try:
        p=urlsplit(str(value or ""))
        if (p.scheme=="https" and p.hostname and
                not p.username and not p.password and
                not p.fragment and len(str(value))<=1200):
            return str(value)
    except ValueError:
        pass
    return ""

def _clean(value, cap=950):
    return " ".join(str(value or "").split())[:cap]

def _safe_csv(value):
    text=str(value or "")
    return "'"+text if text.lstrip().startswith(("=","+","-","@")) else text

def _write(path, records, keys):
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer=csv.DictWriter(fp, fieldnames=keys)
        writer.writeheader()
        for row in records:
            writer.writerow({k:_safe_csv(row.get(k,"")) for k in keys})

def prepare(results, *, today=None):
    root=Path(results)
    if not root.is_dir():raise FileNotFoundError("RESULTS_DIRECTORY_REQUIRED")
    day=_date(today) or dt.date.today()
    general=_read(root/GENERAL_ALL)
    equipment=_read(root/EQUIPMENT_ALL)
    candidate_rows=[];audit=[];counters=Counter();seen=set()
    for lane, data in (("GENERAL_COMMERCIAL",general),
                       ("EQUIPMENT_INTELLIGENCE",equipment)):
        for index,r in enumerate(data):
            counters["all_five_day_rows"]+=1
            scope=_clean(r.get("scope"),1200)
            city=_clean(r.get("city"),90)
            source=_url(r.get("source_url"))
            source_date=_date(r.get("source_event_date"))
            title=_clean(r.get("project_or_company"),220)
            address=_clean(r.get("address_or_company_site_unverified"),220)
            company=(_clean(r.get("company_source_claim"),150)
                     if lane=="EQUIPMENT_INTELLIGENCE" else "")
            stage=_clean(r.get("stage"),150)
            publisher_id=_clean(r.get("source_project_id"),200)
            ident=(city.casefold(), publisher_id.casefold(), source)
            if not publisher_id or not source:
                ident=(city.casefold(),title.casefold(),source)
            fingerprint=hashlib.sha256(
                json.dumps(ident,ensure_ascii=True).encode("utf-8")).hexdigest()[:20]
            project_id=("FRESH_EQUIPMENT:" if lane=="EQUIPMENT_INTELLIGENCE"
                        else "FRESH_GENERAL:")+fingerprint
            record={
                "project_id":project_id,"city":city,"address":address,
                "description":scope,
                "source_id":("official_industrial_announcement"
                             if lane=="EQUIPMENT_INTELLIGENCE"
                             else "municipal_planning_source"),
                "source_keys":publisher_id or title,
                "record_source_url":source,
                "current_source_status":stage,
                "source_record_date":source_date.isoformat() if source_date else "",
                "source_date_basis":_clean(r.get("source_event_date_basis"),130),
                "company_name":company,"lane":lane,
                "freshness_class":_clean(r.get("freshness_class"),140),
                "observation":_clean(r.get("observation"),80),
                "ai_research_priority":"",
            }
            reason=""
            if not source_date or not 0 <= (day-source_date).days <= 4:
                reason="OUTSIDE_FIVE_DAY_SOURCE_EVENT_WINDOW"
            elif not source:
                reason="MISSING_USABLE_EXACT_SOURCE_HTTPS"
            elif not city or len(scope)<35 or not CONCRETE_SCOPE.search(scope):
                reason="INSUFFICIENT_INDUSTRIAL_COMMERCIAL_SCOPE"
            elif lane=="GENERAL_COMMERCIAL" and not address:
                reason="MISSING_PROJECT_ADDRESS"
            elif HOLD_STAGE.search(stage) or str(r.get("decision") or "").upper() in (
                    "RESEARCH_ONLY_COMPLETED_STAGE",
                    "COMPLETED_OR_AWARDED_RESEARCH_ONLY"):
                reason="COMPLETED_OR_AWARDED_NOT_CURRENT_PROCUREMENT"
            elif project_id in seen:
                reason="DUPLICATE_PROJECT_SOURCE"
            scoring=score(record)
            if not reason and (scoring["excluded"] or
                               scoring["score"]<MIN_SELECTION_SCORE):
                reason="BELOW_EXPLAINABLE_COMMERCIAL_SCORE"
            record["ai_research_priority"]=str(scoring["score"])
            accepted=not reason
            audit.append({**record,
                          "qualification":"AI_RESEARCH_QUEUE" if accepted else "HELD_RESEARCH_ONLY",
                          "reason":reason or "SOURCE_BACKED_INVESTIGATION_NOT_VERIFIED_ORDER",
                          "score":scoring["score"],"score_tier":scoring["tier"]})
            if accepted:
                seen.add(project_id)
                candidate_rows.append(record)
                counters[lane+"_eligible"]+=1
            else:
                counters["held_"+reason]+=1
    candidate_rows.sort(key=lambda x:(
        -int(x["ai_research_priority"]),
        0 if x["lane"]=="EQUIPMENT_INTELLIGENCE" else 1,
        x["city"],x["project_id"]))
    _write(root/AI_INPUT,candidate_rows,FIELDS)
    _write(root/AUDIT,audit,AUDIT_FIELDS)
    report={
        "status":"UNCAPPED_FIVE_DAY_AI_RESEARCH_QUEUE_REVIEW_ONLY",
        "run_date":day.isoformat(),
        "selection_window_days_inclusive":5,
        "general_input_rows":len(general),
        "equipment_input_rows":len(equipment),
        "eligible_for_source_backed_ai":len(candidate_rows),
        "held_with_specific_reason":len(audit)-len(candidate_rows),
        "cities_with_eligible_records":sorted({r["city"] for r in candidate_rows}),
        "actual_paid_model_calls":0,
        "buyer_verified":False,"open_supplier_packages_verified":False,
        "outreach_authorized":False,"original_publications_verified":False,
        "counts":dict(counters),
        "outputs":[AI_INPUT,AUDIT,STATUS],
        "warning":"Source-event dates are not proof of first publication; AI findings remain research-only until independent verification.",
    }
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",required=True)
    p.add_argument("--as-of",default=None)
    a=p.parse_args()
    print(json.dumps(prepare(a.results,today=a.as_of),indent=2))

if __name__=="__main__":
    main()
