"""Client-facing *research* shortlist: freshness before project size, no repeats.

Reads preserved Radar outputs and audited report history without network/AI or
database writes. A permit's source-record date is never represented as the
first public announcement; a site merely scanned by Radar is not fresh.
Never automatically mark an internal investigation as a sent client report.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
from pathlib import Path
from collections import Counter

from gta_opportunity_lanes import (
    _csv, _site, _city, _region, _first, PRIVATE_ALL,
)
from gta_freshness import _date

CLIENT_TOP = "GTA_RADAR_CLIENT_FRESH_NONREPEAT_TOP_10.csv"
CLIENT_EXCLUDED = "GTA_RADAR_CLIENT_PREVIOUSLY_REPORTED.csv"
CLIENT_STATUS = "GTA_RADAR_CLIENT_FRESHNESS_STATUS.json"
CLIENT_HTML = "GTA_RADAR_CLIENT_FRESHNESS_REVIEW.html"
ADDITIONAL_HISTORY = "GTA_RADAR_CLIENT_REPORT_HISTORY.csv"
SEED_HISTORY = Path(__file__).resolve().parent / "config" / "client_reported_sites_20261112.csv"
FIELDS = (
    "rank", "opportunity_id", "city", "region", "address", "project_name",
    "nature_of_work", "stage_gate", "named_company_role_unverified",
    "contact_status", "source_event_date", "source_event_date_basis",
    "source_event_age_days", "freshness_priority", "freshness_label",
    "freshness_score_50", "project_size_score_25",
    "project_stage_score_15", "verified_contact_score_10",
    "weighted_score_100", "source_url", "application_ids",
    "procurement_status", "next_verification_action",
)
EXCLUSIONS = ("report_date", "report_name", "city", "address", "opportunity_id",
              "reason")
INACTIVE_STAGES = {"CLOSED_EXCLUDE", "HISTORICAL_APPROVAL_EXCLUDE", "APPEALED_OR_ON_HOLD"}
DECLINE = re.compile(r"\b(?:withdrawn|cancelled|canceled|completed|fully occupied)\b", re.I)
UNKNOWN = ("", "UNKNOWN", "UNVERIFIED", "NOT_AVAILABLE")
DETECTION = re.compile(r"DETECTION|OBSERV|CRAWL|FETCH|SCRAPE|ARCHIV|INDEX_ONLY", re.I)
SCOPE_ONLY = re.compile(r"\b(?:interior alteration|retail unit|store fit.out|"
                        r"washroom|kitchenette|partition|slab reinforcement)\b", re.I)
MAJOR = re.compile(r"\b(?:warehouse|industrial expansion|manufactur\w*|"
                   r"distribution centre|data.cent(?:er|re)|hotel)\b", re.I)


def _site_key(city, address):
    address = re.sub(r"\s+[A-Z]\d[A-Z]\s*$", "", str(address or "").strip(), flags=re.I)
    # Preserve unit-level identities: removing "Unit 103" would merge separate
    # tenant fitouts on the same property.
    return (_city(city, address).casefold(), _site(address))


def _read_history(root, today):
    history={}
    for filename in (SEED_HISTORY, root / ADDITIONAL_HISTORY):
        for row in _csv(filename):
            site=_site_key(row.get("city", ""), row.get("address", ""))
            date=_date(row.get("report_date"))
            if not site[0] or not site[1] or date is None or date > today:
                continue
            history.setdefault(site, []).append({
                "report_date":date.isoformat(),
                "report_name":str(row.get("report_name") or filename.name),
            })
    return history


def _event_index(root, today):
    index={}
    sources=(
        ("GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv","SOURCE_RECORD_DATE_NOT_PUBLICATION_PROOF"),
        ("GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv",
         "OFFICIAL_APPLICATION_OR_PERMIT_EVENT_DATE_NOT_PUBLICATION"),
    )
    for filename, reason in sources:
        for row in _csv(root / filename):
            site=_site_key(row.get("city"), row.get("address"))
            if not site[1] or not site[0]:
                continue
            raw=row.get("source_record_date")
            date=_date(raw)
            if date is None or date > today:
                continue
            observed=row.get("freshness_date_basis") or row.get("date_basis") or ""
            # We always label the result as a source event, not verified first
            # publication, even when the source has a recent filing date.
            if DETECTION.search(str(observed)) and not row.get("source_record_date"):
                continue
            prior=index.get(site)
            entry={
                "date":date,
                "basis":reason,
                "observation":row.get("observation", ""),
                "changed_fields":row.get("changed_fields", ""),
            }
            if prior is None or date > prior["date"]:
                index[site]=entry
    return index


def _size_points(scope, estimated):
    text=" ".join((str(scope or ""), str(estimated or ""))).lower()
    money=re.findall(r"\$\s*(\d+(?:\.\d+)?)\s*(million|m\b|billion|bn\b)",text)
    amounts=[float(value) * (1000 if unit.startswith(("billion","bn")) else 1)
             for value, unit in money]
    if amounts and max(amounts)>=10:
        return 25, "QUANTIFIED_REPORTED_CONSTRUCTION_COST_NOT_CONTRACT"
    squares=re.findall(r"\b([\d,]+(?:\.\d+)?)\s*(?:m²|sq\.?\s*m\.?|sqm|square metres?)\b", text)
    areas=[float(value.replace(",","")) for value in squares]
    if areas and max(areas)>=5000:
        return 25, "QUANTIFIED_LARGE_FLOOR_AREA"
    if areas and max(areas)>=1000:
        return 18, "QUANTIFIED_MEDIUM_FLOOR_AREA"
    if MAJOR.search(text):
        return 14, "INDUSTRIAL_OR_HOSPITALITY_SCOPE_SIZE_UNVERIFIED"
    if SCOPE_ONLY.search(text):
        return 7, "SMALL_OR_TENANT_SCOPE_ESTIMATE_UNVERIFIED"
    return 10, "COMMERCIAL_SCOPE_SIZE_NOT_VERIFIED"


def _stage_points(stage):
    if stage=="PLANNING_OR_SITE_PLAN_REVIEW":return 15
    if stage=="PERMIT_STAGE_VERIFY":return 12
    if stage=="PERMIT_OR_NOAC_ISSUED_VERIFY_PROCUREMENT":return 5
    if stage in INACTIVE_STAGES:return 0
    return 7


def _freshness(row,event,today):
    # Best available evidence: independently verified official posting,
    # otherwise a dated municipal permit/application event. Only the former
    # can say "publication". Never substitute crawler first-seen date.
    published=_date(row.get("source_date")) if row.get(
        "freshness_class")=="OFFICIAL_PUBLICATION_WITHIN_7_DAYS" else None
    if published and 0<=(today-published).days<=7:
        return 0, published, "OFFICIAL_FIRST_PUBLICATION_VERIFIED", 50
    if event:
        days=(today-event["date"]).days
        if days<=7:
            return 1,event["date"],event["basis"],47
        if days<=30:
            return 2,event["date"],event["basis"],34
        if days<=90:
            return 3,event["date"],event["basis"],21
    # A changed page without a dated source event is not a fresh project.
    return 9,None,"NO_RECENT_DOCUMENTED_SOURCE_EVENT",0


def _write(path,fields,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as output:
        writer=csv.DictWriter(output,fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key:("'"+str(row.get(key,"")) if
                                  str(row.get(key,"")).lstrip().startswith(
                                      ("=", "+", "-", "@")) else row.get(key,""))
                             for key in fields})


def run(results, *, today=None):
    root=Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RADAR_RESULTS_REQUIRED")
    today=_date(today) or dt.date.today()
    history=_read_history(root,today)
    events=_event_index(root,today)
    ranked=[]
    removed=[]
    counts=Counter()
    for candidate in _csv(root / PRIVATE_ALL):
        site=_site_key(candidate.get("city"),candidate.get("address"))
        if not site[0] or not site[1]:
            counts["SITE_IDENTITY_INCOMPLETE"]+=1
            continue
        if site in history:
            for matched in history[site]:
                removed.append({
                    **matched,"city":candidate.get("city",""),
                    "address":candidate.get("address",""),
                    "opportunity_id":candidate.get("opportunity_id",""),
                    "reason":"SITE_PREVIOUSLY_INCLUDED_IN_CLIENT_REPORT",
                })
            counts["PREVIOUSLY_REPORTED_PROJECT"]+=1
            continue
        stage=candidate.get("stage_gate","")
        scope=candidate.get("nature_of_work","")
        if stage in INACTIVE_STAGES or DECLINE.search(candidate.get("project_stage","")):
            counts["INACTIVE_OR_PAUSED"]+=1
            continue
        if not _first(candidate.get("source_urls")):
            counts["MISSING_USABLE_OFFICIAL_SOURCE_URL"]+=1
            continue
        band,date,basis,freshness=_freshness(candidate,events.get(site),today)
        if band==9:
            counts["NO_RECENT_DOCUMENTED_SOURCE_EVENT"]+=1
            continue
        size,size_basis=_size_points(scope,candidate.get("estimated_value"))
        stage_score=_stage_points(stage)
        verified_contact=(candidate.get("contact_status")=="PROJECT_ASSIGNED_CONTACT_VERIFIED"
                          and candidate.get("email") and candidate.get("contact_role")
                          and candidate.get("contact_name"))
        contact_points=10 if verified_contact else 0
        points=freshness+size+stage_score+contact_points
        ranked.append({
            "opportunity_id":candidate.get("opportunity_id",""),
            "city":site[0].title(),"region":_region(site[0].title()),
            "address":candidate.get("address",""),
            "project_name":candidate.get("project_name",""),
            "nature_of_work":scope,"stage_gate":stage,
            "named_company_role_unverified":candidate.get("company_name",""),
            "contact_status":candidate.get("contact_status",""),
            "source_event_date":date.isoformat(),
            "source_event_date_basis":basis,
            "source_event_age_days":(today-date).days,
            "freshness_priority":band,
            "freshness_label":(
                "VERIFIED_PUBLICATION_LAST_7_DAYS" if band==0
                else "SOURCE_EVENT_LAST_7_DAYS_NOT_PUBLICATION_PROOF" if band==1
                else "SOURCE_EVENT_8_TO_30_DAYS_NOT_PUBLICATION_PROOF" if band==2
                else "SOURCE_EVENT_31_TO_90_DAYS_NOT_PUBLICATION_PROOF"),
            "freshness_score_50":freshness,
            "project_size_score_25":size,
            "project_stage_score_15":stage_score,
            "verified_contact_score_10":contact_points,
            "weighted_score_100":points,
            "source_url":_first(candidate.get("source_urls")),
            "application_ids":candidate.get("application_ids",""),
            "procurement_status":"UNKNOWN_NOT_VERIFIED_UNAWARDED",
            "next_verification_action":(
                "Verify original filing, stage, developer, actual buying authority "
                "and unawarded supplier packages before commercial outreach. "
                "Size basis: "+size_basis),
        })
    # Freshness is PRIMARY: a recent modest permitted scope outranks an
    # enormous project with a source event older than 30 days. Then we rank
    # useful scope, stage and verified contact only within each freshness tier.
    ranked.sort(key=lambda r:(int(r["freshness_priority"]),
                              -int(r["weighted_score_100"]),
                              int(r["source_event_age_days"]),
                              r["city"],r["address"]))
    chosen=ranked[:10]
    for i,row in enumerate(chosen,1):
        row["rank"]=i
    _write(root/CLIENT_TOP,FIELDS,chosen)
    _write(root/CLIENT_EXCLUDED,EXCLUSIONS,removed)
    result={
        "status":"FRESHNESS_FIRST_CLIENT_INVESTIGATION_REVIEW_ONLY",
        "date":today.isoformat(),
        "top_count":len(chosen),
        "eligible_recent_unreported":len(ranked),
        "source_date_last_7_days":sum(x["freshness_priority"] in (0,1) for x in chosen),
        "verified_original_publications":sum(x["freshness_priority"]==0 for x in chosen),
        "projects_excluded_previously_reported":counts["PREVIOUSLY_REPORTED_PROJECT"],
        "rejected_by_reason":dict(counts),
        "region_distribution":dict(Counter(x["region"] for x in chosen)),
        "freshness_primary":True,
        "score_weights":{"freshness":50,"scope_size":25,"stage":15,"verified_contacts":10},
        "source_date_warning":"Permit/application event date is not verified first-publication date.",
        "buyer_verified_by_this_stage":False,
        "open_unawarded_package_verified_by_this_stage":False,
        "report_history_input":[str(SEED_HISTORY.name),ADDITIONAL_HISTORY],
        "report_history_policy":"Existing client reports excluded; the system NEVER automatically marks unshared candidates as sent.",
        "no_padding_policy":"Return fewer than ten rather than include previously reported or undated/historical projects.",
        "outputs":[CLIENT_TOP,CLIENT_EXCLUDED,CLIENT_HTML],
    }
    (root/CLIENT_STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    esc=lambda x:html.escape(str(x or ""),quote=True)
    pages=["<!doctype html><html><head><meta charset='utf-8'>",
        "<title>GTA Radar — Fresh, non-repeating projects</title>",
        "<style>body{font:15px Segoe UI,Arial;max-width:1160px;margin:28px auto;color:#263238}"
        "table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #ddd}"
        "th{background:#edf2f5}a{color:#116389}</style></head><body>",
        "<h1>Freshness-first client research shortlist</h1>",
        "<p>Non-repeating relative to documented November 10–12 client reports and "
        "the optional local history file. Recent source event is NOT proof of a new "
        "public announcement, buyer, open bid or available contract.</p>",
        "<p>"+str(len(chosen))+" research candidates; "
        +str(counts["PREVIOUSLY_REPORTED_PROJECT"])+" previous sites excluded. "
        "Less than 10 is preferable to fabricated freshness.</p>",
        "<table><tr><th>Priority</th><th>City</th><th>Site / proposed work</th>"
        "<th>Source event</th><th>Score</th><th>Evidence</th></tr>"]
    for row in chosen:
        pages.append("<tr><td>"+esc(row["rank"])+"</td><td>"+esc(row["city"])+
                     "</td><td><b>"+esc(row["address"])+"</b><p>"+
                     esc(row["nature_of_work"][:240])+"</p></td><td>"+
                     esc(row["source_event_date"])+"<small> ("+
                     esc(row["freshness_label"])+")</small></td><td>"+
                     esc(row["weighted_score_100"])+"/100</td><td><a href='"+
                     esc(row["source_url"])+"' rel='noopener noreferrer'>Official source</a></td></tr>")
    pages.append("</table><p><a href='"+CLIENT_TOP+"'>Candidate CSV</a> · "
                 "<a href='"+CLIENT_EXCLUDED+"'>Previously reported exclusions</a> · "
                 "<a href='"+CLIENT_STATUS+"'>Audit and score definitions</a></p></body></html>")
    (root/CLIENT_HTML).write_text("".join(pages),encoding="utf-8")
    # Separate, fail-closed buyer/procurement evidence recheck. No automatic
    # promotion to sale-ready and no existing SQLite / history changes.
    from gta_buyer_verification import run as buyer_review
    result["buyer_verification_review"] = buyer_review(root)
    (root/CLIENT_STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",required=True)
    arguments=p.parse_args()
    print(json.dumps(run(arguments.results),indent=2))
