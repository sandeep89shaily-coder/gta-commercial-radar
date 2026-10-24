"""One concise offline view of all manually run early-cue source batches.

Never report initial baselines as NEW, never infer live buying contracts from
planning records, and never turn a failed publisher into 0 opportunities.
"""
from __future__ import annotations
import csv
import datetime as dt
import re
from pathlib import Path

HEALTH_FILES=(
    "EARLY_SIGNALS_SOURCES_STATUS.csv",
    "EARLY_CUES_SOURCE_STATUS.csv",
    "EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv",
    "EARLY_DISCOVERY_SOURCE_STATUS.csv",
    "EARLY_INVESTMENT_TENDERS_STATUS.csv",
    "EARLY_AIC_EMAIL_STATUS.csv",
    "EARLY_AJAX_SOURCE_STATUS.csv",
    "EARLY_OAKVILLE_SOURCE_STATUS.csv",
    "EARLY_HAMILTON_SOURCE_STATUS.csv",
    "EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv",
)
SOURCE_HINTS={
    "brampton_preconsultation":16,
    "burlington_ward_discovery":15,
    "brampton_planning_agendas":15,
    "milton_notices":13,
    "pickering_proposals":13,
    "oakville_development":12,
    "hamilton_planning_notices":15,
    "hamilton_applications_gis":12,
    "ero_proposal_watch":11,
    "ontario_investment_news":11,
    "ieso_connections":10,
    "burlington_project_pages":10,
    "toronto_development":7,
}
OUTPUT_COLUMNS=("research_rank","priority","source_id","item_id","city",
     "site","title","application_date","public_posting_date","radar_first_seen",
     "matched_sources","official_source_url","published_entity",
     "lead_status","why_research","missing_verification")
SCOPES=re.compile(r"\b(?:industrial|warehouse|manufactur\w*|factory|"
  r"cold[- ]storage|refrigerat\w*|loading docks?|hotel|commercial facility|"
  r"production line|logistic\w*|plant expansion|data cent(?:er|re)|"
  r"power generation|industrial equip\w*)\b",re.I)
RESIDENTIAL=re.compile(r"\b(?:residential|apartment|townhouse|"
                       r"condominium|housing|dwelling)\b",re.I)


def _rows(filename):
    try:
        with Path(filename).open("r",encoding="utf-8-sig",newline="") as f:
            return list(csv.DictReader(f))
    except (OSError,csv.Error,UnicodeError):
        return None


def statuses(result_dir):
    result_dir=Path(result_dir)
    findings=[]
    for name in HEALTH_FILES:
        entries=_rows(result_dir/name)
        if entries is None:
            findings.append((name,"NOT_RUN_OR_UNREADABLE",""))
            continue
        if not entries:
            findings.append((name,"EMPTY_STATUS_FILE",""))
        for item in entries:
            sid=item.get("source_id","UNKNOWN")
            state=item.get("state",item.get("status","UNKNOWN"))
            findings.append((sid,state,item.get("error","")))
    return findings


def _date(value):
    try:
        return dt.date.fromisoformat(str(value or "").strip())
    except (ValueError,TypeError):
        return None


def priority(row,today):
    """Freshness is mandatory for shortlist. Receipt != public posting.

    First radar observation during bulk baseline is NOT a new project.
    Undated and old records remain in historical research, not top 50.
    """
    sid=row.get("source_id","")
    title=row.get("title","")
    posted_day=_date(row.get("official_public_posting_date"))
    application_day=_date(row.get("application_date"))
    public_age=(today-posted_day).days if posted_day else None
    received_age=(today-application_day).days if application_day else None
    if public_age is not None and 0<=public_age<=180:
        freshness=95 if public_age<=30 else 80 if public_age<=90 else 58
        reason="OFFICIAL_PUBLIC_POST_WITHIN_180_DAYS"
    elif received_age is not None and 0<=received_age<=180:
        freshness=60 if received_age<=30 else 50 if received_age<=90 else 38
        reason="RECENT_APPLICATION_RECEIPT_NOT_PUBLICATION_DATE"
    else:
        return 0,"HISTORICAL_OR_NO_VERIFIED_RECENT_PROJECT_DATE"
    # Location not established (many Ontario-wide ERO and federal tenders):
    # do not crowd locally verifiable GTA projects into a top-50 product.
    city=str(row.get("city") or "").upper().strip()
    if not city:
        return 0,"LOCATION_NOT_VERIFIED_REVIEW_SEPARATELY"
    # Do not treat government procurement outside GTA as new private building.
    if sid=="federal_open_tenders":
        return 0,"FEDERAL_TENDER_SEPARATE_REVIEW_LANE"
    score=SOURCE_HINTS.get(sid,4)+freshness
    if row.get("site"):score+=9
    if row.get("record_url"):score+=5
    if row.get("published_entity"):score+=3
    if SCOPES.search(title):score+=14
    if RESIDENTIAL.search(title):score-=25
    if row.get("commercial_signal")=="MIXED_USE_REVIEW":score-=8
    return max(score,0),reason


def preview_candidates(records,limit=50,today=None):
    today=today or dt.datetime.now(dt.timezone.utc).date()
    candidates=[]
    seen=set()
    for row in records:
        sid=row.get("source_id") or ""
        rid=row.get("item_id") or ""
        if (sid,rid) in seen or not sid or not rid:continue
        seen.add((sid,rid))
        score,date_basis=priority(row,today)
        if row.get("lead_status")!="NOT_SALE_READY_RESEARCH_ONLY":continue
        if not row.get("record_url"):continue
        if score<30:continue
        candidates.append(dict(
           research_rank=score,
           priority="RESEARCH_FIRST" if score>=60 else "RESEARCH_LATER",
           source_id=sid,item_id=rid,city=row.get("city",""),
           site=row.get("site",""),title=row.get("title",""),
           application_date=row.get("application_date",""),
           public_posting_date=row.get("official_public_posting_date",""),
           radar_first_seen=row.get("radar_first_seen",""),
           matched_sources=row.get("matched_sources",""),
           official_source_url=row.get("record_url",""),
           published_entity=row.get("published_entity",""),
           lead_status="NOT_SALE_READY_RESEARCH_ONLY",
           why_research=date_basis,
           missing_verification="Verify current live scope; legal buyer/operator; "
             "original public contact; procurement/work package; supplier status"))
    candidates.sort(key=lambda x:(-int(x["research_rank"]),
                     x["source_id"],x["item_id"]))
    return candidates[:limit]


def run(result_dir="GTA_RADAR_RESULTS",limit=50):
    out=Path(result_dir);out.mkdir(parents=True,exist_ok=True)
    health=statuses(out)
    lines=["GTA RADAR - EARLY PUBLIC INTELLIGENCE PILOT",
     "Manual / review-only / no paid AI / no V8 change",
     "Source health (NOT_RUN is not ZERO leads):"]
    for sid,state,error in health:
        lines.append(f"- {sid}: {state}"+(" ["+error[:100]+"]" if error else ""))
    rows=_rows(out/"EARLY_EVIDENCE_ACTIONABILITY_GATES.csv")
    if rows is None:
        lines.append("Evidence review missing: run early_evidence_match.py after source runs.")
        top=[]
    else:
        top=preview_candidates(rows,limit=limit)
        lines.append(f"Potential RESEARCH candidates selected: {len(top)}")
    lines.append("VERIFIED BUYERS/UNAWARDED PRIVATE CONTRACTS: not established by this report.")
    lines.append("Follow roadmap: source advantage -> 10 verified opportunities -> 2 paying pilots.")
    (out/"EARLY_PILOT_RUN_SUMMARY.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    temp=out/"EARLY_TOP_RESEARCH_PREVIEW.csv.tmp"
    with temp.open("w",encoding="utf-8-sig",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=OUTPUT_COLUMNS,extrasaction="ignore")
        writer.writeheader();writer.writerows(top)
    temp.replace(out/"EARLY_TOP_RESEARCH_PREVIEW.csv")
    print("\n".join(lines[-5:]))
    return 0


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    p.add_argument("--limit",type=int,default=50)
    args=p.parse_args()
    if args.limit<1 or args.limit>200:p.error("limit must be 1..200")
    raise SystemExit(run(args.output_dir,args.limit))
