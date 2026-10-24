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


def priority(row,today):
    sid=row.get("source_id","")
    when=row.get("official_public_posting_date","")
    title=row.get("title","")
    score=SOURCE_HINTS.get(sid,4)
    if row.get("site"):score+=9
    if row.get("city"):score+=4
    if row.get("record_url"):score+=5
    if row.get("matched_sources"):score+=3
    if row.get("published_entity"):score+=4
    if SCOPES.search(title):score+=23
    if RESIDENTIAL.search(title):score-=10
    posted=""
    try:
        day=dt.date.fromisoformat(when)
        age=(today-day).days
        if 0<=age<=30:score+=25;posted="OFFICIAL_POST_LAST_30_DAYS"
        elif 31<=age<=90:score+=16;posted="OFFICIAL_POST_LAST_90_DAYS"
        elif 91<=age<=365:score+=5;posted="OFFICIAL_POST_LAST_YEAR"
        else:posted="OLDER_PUBLIC_DATE"
    except (TypeError,ValueError):
        posted="NO_VERIFIED_PUBLICATION_DATE"
    return max(score,0),posted


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
