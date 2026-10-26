"""Preserve distinct early-stage pilot signals when joining the common V8 selector."""
import csv
from datetime import datetime, timezone
from pathlib import Path
PAIRS=[("EARLY_SIGNALS_SOURCES_STATUS.csv","EARLY_SIGNALS_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_CUES_SOURCE_STATUS.csv","EARLY_CUES_CHANGES_REVIEW_ONLY.csv","state"),("EARLY_DISCOVERY_SOURCE_STATUS.csv","EARLY_DISCOVERY_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_HAMILTON_SOURCE_STATUS.csv","EARLY_HAMILTON_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv","EARLY_PUBLIC_NOTICES_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_OAKVILLE_SOURCE_STATUS.csv","EARLY_OAKVILLE_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_AJAX_SOURCE_STATUS.csv","EARLY_AJAX_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_INVESTMENT_TENDERS_STATUS.csv","EARLY_INVESTMENT_TENDERS_CHANGES.csv","status"),("EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv","EARLY_MARKHAM_NEW_REPORTS_REVIEW_ONLY.csv","status")]
FIELDS=["source_id","source_key","source_group","description","address","city","company_name","event_date","event_date_basis","evidence_url","source_record_date","current_source_status","early_signal_stage","early_signal_type","first_observed_at","pre_permit_verification","procurement_status"]
def read(path):
    if not Path(path).is_file(): return []
    with Path(path).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
STEP_NAMES=("early_planning_pilot","early_industrial_cues","early_agendas","early_hamilton","early_notices","early_oakville","early_ajax","early_investment_tenders","early_markham")
REVIEW_FIELDS=["source_id","source_key","observed_at","change_type","stage",
              "source_record_date","description","site","evidence_url",
              "commercial_fit","pipeline_disposition","pre_permit_verification",
              "procurement_status"]
REVIEW_ONLY_SOURCES={"EARLY_INVESTMENT_TENDERS_STATUS.csv",
                     "EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv"}

def review_changes(folder,successful_steps,run_started,accepted):
    """One current-run review of signals from all nine runner groups.

    Keep weak/document sources visible, never buy research based solely
    on an index, news item or a government open tender.
    """
    folder=Path(folder)
    baseline=as_utc(run_started)
    promoted={(r["source_id"],r["source_key"]) for r in accepted}
    records=[]
    seen=set()
    for i,(status_file,event_file,column) in enumerate(PAIRS):
        if STEP_NAMES[i] not in successful_steps:
            continue
        live={row.get("source_id") for row in read(folder/status_file)
              if row.get(column) in ("SUCCESS","SUCCESS_INDEX_ONLY","SUCCESS_REPORT_INDEX")}
        for row in read(folder/event_file):
            sid=row.get("source_id") or ""
            key=row.get("record_id") or row.get("application_id") or row.get("feature_id") or ""
            stamp=row.get("observed_at") or ""
            changed=row.get("change_type","").upper()
            when=as_utc(stamp)
            if not sid or not key or sid not in live or changed not in ("NEW","UPDATED"):
                continue
            if baseline is not None and (when is None or when<baseline):
                continue
            if (sid,key) in seen:
                continue
            seen.add((sid,key))
            use=(row.get("commercial_fit") or row.get("commercial_signal") or "").upper()
            if (sid,key) in promoted:
                disposition="EARLY_SELECTOR_CANDIDATE"
            elif "CALENDAR_ONLY" in key:
                disposition="CALENDAR_ONLY_REVIEW"
            elif use in ("LOW","RESIDENTIAL_LIKELY"):
                disposition="RESIDENTIAL_EXCLUDED"
            elif status_file in REVIEW_ONLY_SOURCES:
                disposition="DOCUMENT_OR_TENDER_REVIEW_ONLY"
            elif use in ("UNKNOWN","USE_UNKNOWN","REVIEW",""):
                disposition="COMMERCIAL_USE_UNCONFIRMED"
            else:
                disposition="INCOMPLETE_OR_UNQUALIFIED_CUE"
            records.append({
                "source_id":sid,"source_key":key,"observed_at":stamp,
                "change_type":changed,"stage":row.get("stage") or "",
                "source_record_date":row.get("source_application_date") or row.get("source_date") or "",
                "description":row.get("description") or row.get("title") or "",
                "site":row.get("site") or row.get("location") or "",
                "evidence_url":row.get("source_url") or "",
                "commercial_fit":use,"pipeline_disposition":disposition,
                "pre_permit_verification":"NOT_VERIFIED",
                "procurement_status":row.get("procurement_status") or "UNKNOWN",
            })
    return records

def as_utc(stamp):
    if not stamp:return None
    try:
        result=datetime.fromisoformat(str(stamp).replace("Z","+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except ValueError:return None

def write_csv(path,fields,rows):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)

def harvest(folder,successful_steps=None,run_started=None):
    start=as_utc(run_started)
    folder=Path(folder);events=[];seen=set();statuses=[]
    for i,(sf,ef,col) in enumerate(PAIRS):
        if successful_steps is not None and STEP_NAMES[i] not in successful_steps:
            statuses.append({"source_file":sf,"accepted":0,"status_file_present":(folder/sf).exists(),"reason":"NOT_SUCCESSFUL_THIS_RUN"})
            continue
        allowed={r.get("source_id") for r in read(folder/sf) if r.get(col) in ("SUCCESS","SUCCESS_INDEX_ONLY","SUCCESS_REPORT_INDEX")}
        n=0
        for r in read(folder/ef):
            sid=r.get("source_id","");key=r.get("record_id") or r.get("application_id") or r.get("feature_id") or ""
            if sid not in allowed or not sid or not key or (sid,key) in seen:continue
            if r.get("change_type","").upper() not in ("NEW","UPDATED"):continue
            if start is not None:
                seen_at=as_utc(r.get("observed_at"))
                if seen_at is None or seen_at < start:continue
            if "CALENDAR_ONLY" in key or r.get("commercial_fit") in ("LOW","RESIDENTIAL_LIKELY","UNKNOWN","REVIEW") or r.get("commercial_signal")=="RESIDENTIAL_LIKELY":continue
            # Tenders/news are kept in a separate reviewed lane; they cannot
            # become leads solely because a procurement notice was observed.
            if sf in ("EARLY_INVESTMENT_TENDERS_STATUS.csv","EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv"):continue
            if sf=="EARLY_AJAX_SOURCE_STATUS.csv" and r.get("commercial_fit") not in ("POSSIBLE_COMMERCIAL","COMMERCIAL","INDUSTRIAL","MIXED_USE_REVIEW"):continue
            if sf=="EARLY_OAKVILLE_SOURCE_STATUS.csv" and r.get("commercial_fit") not in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"):continue
            desc=r.get("description") or r.get("title") or ""
            url=r.get("source_url") or ""
            if not desc.strip() or not url.startswith("https://"):continue
            seen.add((sid,key));n+=1
            events.append(dict(source_id=sid,source_key=key,source_group="EARLY_PILOT_OBSERVED_CHANGE",
                description=desc,address=r.get("location") or r.get("site") or "",
                city=r.get("city") or "",company_name=r.get("company") or r.get("published_company_unverified_role") or "",
                event_date=(r.get("observed_at") or "")[:10],
                event_date_basis="RADAR_OBSERVATION_NOT_PUBLICATION_DATE",
                evidence_url=url,source_record_date=r.get("source_application_date") or r.get("source_date") or "",
                current_source_status=r.get("status") or r.get("stage") or "UNKNOWN",
                early_signal_stage=r.get("stage") or "STAGE_NOT_REPORTED",
                early_signal_type=r.get("signal_type") or "UPSTREAM_PUBLIC_OBSERVATION",
                first_observed_at=r.get("observed_at") or "",
                # The goal is to discover activity before permits, but the
                # source observation is NOT evidence no permit exists yet.
                pre_permit_verification="NOT_VERIFIED",
                procurement_status=r.get("procurement_status") or "UNKNOWN"))
        statuses.append({"source_file":sf,"accepted":n,"status_file_present":(folder/sf).exists()})
    return events,statuses
def merge(original,folder,destination,successful_steps=None,run_started=None):
    base=read(original);events,audit=harvest(folder,successful_steps=successful_steps,run_started=run_started)
    keys={(r.get("source_id"),r.get("source_key")) for r in base}
    extra=[r for r in events if (r["source_id"],r["source_key"]) not in keys]
    rows=base+extra;columns=list(dict.fromkeys(k for row in rows for k in row)) or FIELDS
    dest=Path(destination);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    # The pilot review lane records every *current-run* upstream cue, including
    # unqualified documents and unknown uses. Nothing here is sale-ready.
    # When a standalone caller intentionally omits successful_steps, review
    # only this invocation's harvested source groups (same harvest semantics).
    active=successful_steps if successful_steps is not None else set(STEP_NAMES)
    review_rows=review_changes(folder,active,run_started,events)
    write_csv(Path(folder)/"GTA_RADAR_EARLY_CUES_REVIEW.csv",REVIEW_FIELDS,review_rows)
    return dest,{"early_pilot_changes_accepted":len(extra),"early_pilot_audit":audit,
                 "early_cues_reviewed":len(review_rows),
                 "early_cues_review_only":sum(r["pipeline_disposition"]!="EARLY_SELECTOR_CANDIDATE" for r in review_rows)}
