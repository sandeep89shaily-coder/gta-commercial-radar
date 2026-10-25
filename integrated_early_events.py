"""Review-only bridge from independently run early collectors into the V8 selector."""
import csv
from datetime import datetime, timezone
from pathlib import Path
PAIRS=[("EARLY_SIGNALS_SOURCES_STATUS.csv","EARLY_SIGNALS_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_CUES_SOURCE_STATUS.csv","EARLY_CUES_CHANGES_REVIEW_ONLY.csv","state"),("EARLY_DISCOVERY_SOURCE_STATUS.csv","EARLY_DISCOVERY_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_HAMILTON_SOURCE_STATUS.csv","EARLY_HAMILTON_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv","EARLY_PUBLIC_NOTICES_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_OAKVILLE_SOURCE_STATUS.csv","EARLY_OAKVILLE_CHANGES_REVIEW_ONLY.csv","status"),("EARLY_AJAX_SOURCE_STATUS.csv","EARLY_AJAX_CHANGES_REVIEW_ONLY.csv","status")]
FIELDS=["source_id","source_key","source_group","description","address","city","company_name","event_date","event_date_basis","evidence_url","source_record_date","current_source_status"]
def read(path):
    if not Path(path).is_file(): return []
    with Path(path).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
STEP_NAMES=("early_planning_pilot","early_industrial_cues","early_agendas","early_hamilton","early_notices","early_oakville","early_ajax")
def harvest(folder,successful_steps=None,run_started=None):
    def as_utc(stamp):
        if not stamp:return None
        try:
            result=datetime.fromisoformat(str(stamp).replace("Z","+00:00"))
            return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
        except ValueError:return None
    start=as_utc(run_started)
    folder=Path(folder);events=[];seen=set();statuses=[]
    for i,(sf,ef,col) in enumerate(PAIRS):
        if successful_steps is not None and STEP_NAMES[i] not in successful_steps:
            statuses.append({"source_file":sf,"accepted":0,"status_file_present":(folder/sf).exists(),"reason":"NOT_SUCCESSFUL_THIS_RUN"})
            continue
        allowed={r.get("source_id") for r in read(folder/sf) if r.get(col) in ("SUCCESS","SUCCESS_INDEX_ONLY")}
        n=0
        for r in read(folder/ef):
            sid=r.get("source_id","");key=r.get("record_id") or r.get("application_id") or r.get("feature_id") or ""
            if sid not in allowed or not sid or not key or (sid,key) in seen:continue
            if r.get("change_type","").upper() not in ("NEW","UPDATED"):continue
            if start is not None:
                seen_at=as_utc(r.get("observed_at"))
                if seen_at is None or seen_at < start:continue
            if "CALENDAR_ONLY" in key or r.get("commercial_fit") in ("LOW","RESIDENTIAL_LIKELY","UNKNOWN","REVIEW") or r.get("commercial_signal")=="RESIDENTIAL_LIKELY":continue
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
                current_source_status=r.get("status") or r.get("stage") or "UNKNOWN"))
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
    return dest,{"early_pilot_changes_accepted":len(extra),"early_pilot_audit":audit}
