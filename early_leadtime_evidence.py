"""Auditable measured early disclosure advantage; no invented posting dates.

The raw cross-source matcher only knows same-address POSSIBLE links. A reviewer
must establish the SAME physical project with official evidence and enter both
public posting dates. Do not compare application receipt vs newsletter date
or pretend a plan submission date was an official permit publication date.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
from pathlib import Path
from urllib.parse import urlparse

FIELDS=("city","normalized_site","first_source","first_record_id",
 "other_source","other_record_id","first_official_link","other_official_link",
 "same_project_reviewed","identity_evidence_url",
 "earlier_public_date","earlier_public_event_type","earlier_public_notice_url",
 "later_public_date","later_public_event_type","later_public_notice_url",
 "reviewer","reviewed_on","measurement_status","lead_days","reviewer_notes")
OUT=("city","normalized_site","first_source","other_source",
 "lead_days","measurement_status","early_event","later_event",
 "early_evidence","later_evidence","identity_evidence","reviewer")
STATUS=("metric","value","caveat")
EARLY={"PRE_APPLICATION_PUBLIC_NOTICE","COUNCIL_AGENDA_PUBLISHED",
       "PLANNING_APPLICATION_PUBLIC_POSTED","ENVIRONMENTAL_PROPOSAL_POSTED",
       "UTILITY_CONNECTION_QUEUE_PUBLIC_POSTED","PUBLIC_INVESTMENT_ANNOUNCEMENT"}
LATER={"BUILDING_PERMIT_FIRST_PUBLIC_POSTED",
       "FORMAL_SITE_PLAN_FIRST_PUBLIC_POSTED",
       "TENDER_FIRST_PUBLIC_POSTED"}
EMPTY={"","UNKNOWN","NO","UNVERIFIED"}

def _read(path):
    path=Path(path)
    if not path.is_file():return None
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def _write(path,fields,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+".tmp")
    with temp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(rows)
    temp.replace(p)

def _https(url):
    try:
        p=urlparse(str(url or ""))
        return p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
    except (TypeError,ValueError):return False

def _date(raw):
    try:
        return dt.date.fromisoformat(str(raw or "").strip())
    except (TypeError,ValueError):return None

def _key(r):
    a=(r.get("first_source",""),r.get("first_record_id",""))
    b=(r.get("other_source",""),r.get("other_record_id",""))
    return tuple(sorted((a,b)))

def _fresh(pair):
    return dict(city=pair.get("city",""),
      normalized_site=pair.get("normalized_site",""),
      first_source=pair.get("first_source",""),
      first_record_id=pair.get("first_record_id",""),
      other_source=pair.get("other_source",""),
      other_record_id=pair.get("other_record_id",""),
      first_official_link=pair.get("first_official_link",""),
      other_official_link=pair.get("other_official_link",""),
      same_project_reviewed="NO",identity_evidence_url="",
      earlier_public_date="",earlier_public_event_type="",
      earlier_public_notice_url="",later_public_date="",
      later_public_event_type="",later_public_notice_url="",
      reviewer="",reviewed_on="",measurement_status="NOT_MEASURED",lead_days="",
      reviewer_notes="")

def merge(matches,prior):
    old={_key(r):r for r in prior if all(_key(r)[0]) and all(_key(r)[1])}
    result=[];seen=set()
    for pair in matches:
        key=_key(pair)
        if key in seen or not all(key[0]) or not all(key[1]):continue
        seen.add(key)
        row=_fresh(pair)
        if key in old:
            for field in FIELDS[8:]:
                if field not in ("measurement_status","lead_days"):
                    row[field]=old[key].get(field,row[field])
        result.append(row)
    # Preserve human reviews of pairs absent from an incomplete new scan.
    for key,prev in old.items():
        if key in seen:continue
        row={f:prev.get(f,"") for f in FIELDS}
        note="PAIR_NOT_PRESENT_IN_LATEST_MATCH_SCAN"
        if note not in row["reviewer_notes"]:
            row["reviewer_notes"]=(row["reviewer_notes"]+" | "+note).strip(" |")
        result.append(row)
    return result

def measure(row,today=None):
    today=today or dt.datetime.now(dt.timezone.utc).date()
    if str(row.get("same_project_reviewed","")).upper()!="YES":
        return "SAME_PROJECT_NOT_VERIFIED",""
    if not all(_https(row.get(field)) for field in (
        "identity_evidence_url","earlier_public_notice_url","later_public_notice_url")):
        return "MISSING_OFFICIAL_LINK_EVIDENCE",""
    if not str(row.get("reviewer") or "").strip() or not _date(row.get("reviewed_on")):
        return "MISSING_DATED_REVIEWER",""
    if _date(row["reviewed_on"])>today:return "FUTURE_REVIEW_DATE",""
    if row.get("earlier_public_event_type") not in EARLY:
        return "EARLY_EVENT_TYPE_NOT_COMPARABLE",""
    if row.get("later_public_event_type") not in LATER:
        return "LATER_EVENT_TYPE_NOT_COMPARABLE",""
    first=_date(row.get("earlier_public_date"))
    second=_date(row.get("later_public_date"))
    if not first or not second or first>today or second>today:
        return "PUBLICATION_DATES_UNVERIFIED",""
    days=(second-first).days
    if days<0:return "LATER_EVENT_PUBLISHED_FIRST_REVIEW",str(days)
    # This is reviewer-supplied, not independently authenticated by the code.
    return "REVIEWER_ATTESTED_DATE_COMPARISON_VERIFY_URLS",str(days)

def run(match_file="GTA_RADAR_RESULTS/EARLY_SOURCE_CROSS_MATCH_REVIEW.csv",
        out_dir="GTA_RADAR_RESULTS"):
    matches=_read(match_file)
    if matches is None:
        print("No source cross-match data. Run the isolated evidence matcher first.")
        return 1
    root=Path(out_dir);root.mkdir(parents=True,exist_ok=True)
    path=root/"EARLY_LEADTIME_EVIDENCE_WORKSHEET.csv"
    rows=merge(matches,_read(path) or [])
    output=[]
    for r in rows:
        state,days=measure(r)
        r["measurement_status"]=state;r["lead_days"]=days
        if days:
            output.append(dict(city=r["city"],normalized_site=r["normalized_site"],
                 first_source=r["first_source"],other_source=r["other_source"],
                 lead_days=days,measurement_status=state,
                 early_event=r["earlier_public_event_type"],
                 later_event=r["later_public_event_type"],
                 early_evidence=r["earlier_public_notice_url"],
                 later_evidence=r["later_public_notice_url"],
                 identity_evidence=r["identity_evidence_url"],reviewer=r["reviewer"]))
    _write(path,FIELDS,rows)
    _write(root/"EARLY_LEADTIME_REVIEW_MEASUREMENTS.csv",OUT,output)
    confirmed=[r for r in output if r["measurement_status"]==
       "REVIEWER_ATTESTED_DATE_COMPARISON_VERIFY_URLS"]
    positive=[int(r["lead_days"]) for r in confirmed if int(r["lead_days"])>0]
    positive.sort()
    report=[
       dict(metric="potential_same_address_pairs",value=len(matches),
          caveat="Cross-source address matches are not verified same project"),
       dict(metric="reviewer_attested_date_comparisons",value=len(confirmed),
          caveat="Self-entered date evidence, requiring independent URL checks"),
       dict(metric="positive_early_disclosure_examples",value=len(positive),
          caveat="Only pairs with actual first public-posted event dates and comparison"),
       dict(metric="median_attested_advance_days",value=positive[len(positive)//2] if positive else "",
          caveat="Research signal only; not proof the trade was unawarded"),
    ]
    _write(root/"EARLY_LEADTIME_EVIDENCE_SUMMARY.csv",STATUS,report)
    print("Lead-time candidate pairs",len(matches),"with reviewer-entered comparable dates",
          len(confirmed),"| no inferred public posting dates")
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cross-match",default="GTA_RADAR_RESULTS/EARLY_SOURCE_CROSS_MATCH_REVIEW.csv")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args()
    raise SystemExit(run(a.cross_match,a.output_dir))
