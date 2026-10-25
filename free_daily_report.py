"""Zero-DeepSeek daily public-source watch, independent of historical AI research.

Only collector/V4 selector input is used. "First observed" means Radar first
saw the source record, NOT the municipality issued a permit today or an
unawarded contract is available. Records from the regional archive are never
represented as newly discovered permit events merely from being imported.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import urlparse

from commercial_selector_v4 import ACTION
from opportunity_lifecycle import classify_status

FIELDS=[
    "observation","first_seen_local","last_seen_local","project_id","address",
    "city","source_id","source_keys","lane","description","event_date",
    "date_basis","source_record_date","current_source_status",
    "stage_from_local_status","record_source_url","record_source_url_basis",
    "service_hypotheses","source_group","review_priority",
    "early_signal_stage","first_observed_at","pre_permit_verification",
    "procurement_status","follow_up","warning"
]
WATCHED_LANES={"EARLY_SIGNAL_WATCH","PERMIT_REVIEW","PLANNING_WATCH",
               "BUSINESS_REVIEW","ENVIRONMENT_WATCH"}
STATE_NAME="GTA_RADAR_FREE_DAILY_SEEN.json"
CSV_NAME="GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"
HTML_NAME="GTA_RADAR_DAILY_NEW_DEVELOPMENTS.html"
ALL_NAME="GTA_RADAR_DAILY_PUBLIC_RECORDS.csv"

def _read(path):
    p=Path(path)
    if not p.is_file():raise FileNotFoundError(str(path))
    with p.open(encoding="utf-8-sig",newline="") as fh:
        return list(csv.DictReader(fh))

def _write(path,rows):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=FIELDS,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)

def _sig(row):
    # Use substantive record changes, NOT rolling detection date or AI prose.
    values=[row.get(k) or "" for k in
            ("source_id","source_keys","description","current_source_status","company_name")]
    clean=[" ".join(str(v).casefold().split()) for v in values]
    return hashlib.sha256(json.dumps(clean,ensure_ascii=True).encode()).hexdigest()

def _record(row,observation,first,day):
    status=row.get("current_source_status") or ""
    stage=classify_status(status)
    desc=row.get("description") or ""
    lane=row.get("lane") or ""
    if stage in ("COMPLETED","BLOCKED_OR_INACTIVE"):
        next_action="Historical/inactive; do not promote as a current service opportunity."
    elif stage=="INSPECTION_STAGE":
        next_action="Construction may be advanced; check only outstanding future packages."
    elif lane=="EARLY_SIGNAL_WATCH":
        next_action=("Identify the project sponsor and actual purchasing decision-maker; "
                     "verify whether supplier selection has started, packages remain open, "
                     "and whether any permit has already been issued.")
    elif lane in WATCHED_LANES and ACTION.search(desc):
        next_action="Verify exact official permit, project company and whether supplier work remains unawarded."
    else:
        next_action="Check if this record contains specific new commercial work before pursuing."
    if observation=="ARCHIVE_CONTEXT":
        next_action="Historical source-dated regional record; not a new municipal event. "+next_action
    return {
        "observation":observation,"first_seen_local":first,"last_seen_local":day,
        "project_id":row.get("project_id",""),"address":row.get("address",""),
        "city":row.get("city",""),"source_id":row.get("source_id",""),
        "source_keys":row.get("source_keys",""),"lane":lane,
        "description":desc,"event_date":row.get("event_date",""),
        "date_basis":row.get("date_basis",""),
        "source_record_date":row.get("source_record_date",""),
        "current_source_status":status,"stage_from_local_status":stage,
        "record_source_url":row.get("record_source_url",""),
        "record_source_url_basis":row.get("record_source_url_basis",""),
        "service_hypotheses":row.get("service_hypotheses",""),
        "source_group":row.get("source_group",""),
        "review_priority":row.get("review_priority",""),
        "early_signal_stage":row.get("early_signal_stage",""),
        "first_observed_at":row.get("first_observed_at",""),
        "pre_permit_verification":row.get("pre_permit_verification",""),
        "procurement_status":row.get("procurement_status",""),
        "follow_up":next_action,
        "warning":("Source observation/status is not a live government verification, "
                   "a newly issued permit, or evidence of a supplier contract.")
    }

def _priority(row):
    # Prioritize substantive early-stage changes without claiming live stage.
    kind={"FIRST_OBSERVED":0,"RECORD_CHANGED":1,"INITIAL_BASELINE":2,
          "ARCHIVE_CONTEXT":3,"UNCHANGED":4}.get(row["observation"],5)
    stage={"PRE_APPROVAL":0,"PRE_ISSUANCE":1,"APPROVED_NOT_ISSUED":2,
           "PERMIT_ISSUED":3,"UNKNOWN":4,"INSPECTION_STAGE":5,
           "BLOCKED_OR_INACTIVE":9,"COMPLETED":9}.get(row["stage_from_local_status"],5)
    try:base=-int(row["review_priority"])
    except (ValueError,TypeError):base=0
    early_rank=0 if row["lane"]=="EARLY_SIGNAL_WATCH" else 1
    return (kind,early_rank,stage,base,row["project_id"])

def build(candidates_path,results_dir,*,today=None):
    """Update persistent first-seen index only after parsing the latest V4 file.

    On the initial run the current dataset is a baseline, not falsely called
    'new'. No queue, collector SQLite, DeepSeek ledger, or AI history is changed.
    """
    day=(today or dt.date.today()).isoformat()
    out=Path(results_dir)
    out.mkdir(parents=True,exist_ok=True)
    source=_read(candidates_path)
    state_path=out/STATE_NAME
    initialized=state_path.exists()
    previous={}
    if initialized:
        prior=json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(prior,dict) or prior.get("schema")!=1:
            raise ValueError("Unknown saved free-watch state; refusing to overwrite")
        previous=prior.get("seen",{})
        if not isinstance(previous,dict):
            raise ValueError("Invalid saved free-watch state")
    updated=dict(previous)
    full=[]
    active=[]
    count={"FIRST_OBSERVED":0,"RECORD_CHANGED":0,"INITIAL_BASELINE":0,
           "ARCHIVE_CONTEXT":0,"UNCHANGED":0}
    for raw in source:
        pid=str(raw.get("project_id") or "").strip()
        if not pid:continue
        archived=raw.get("source_group")=="REGIONAL_ARCHIVED_SOURCE"
        fp=_sig(raw)
        old=previous.get(pid,{})
        if not isinstance(old,dict):old={}
        if archived and not old:
            observation="ARCHIVE_CONTEXT"
        elif not initialized and not archived:
            observation="INITIAL_BASELINE"
        elif not old:
            observation="FIRST_OBSERVED"
        elif fp!=old.get("fingerprint"):
            observation="RECORD_CHANGED"
        else:
            observation="UNCHANGED"
        first=old.get("first_seen_local") or day
        updated[pid]={"fingerprint":fp,"first_seen_local":first,
                      "last_seen_local":day}
        row=_record(raw,observation,first,day)
        full.append(row)
        count[observation]+=1
        if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):
            active.append(row)
    active.sort(key=_priority)
    full.sort(key=_priority)
    _write(out/CSV_NAME,active)
    _write(out/ALL_NAME,full)
    state_tmp=state_path.with_suffix(".tmp")
    state_tmp.write_text(json.dumps({"schema":1,"last_run_local":day,"seen":updated},
                                    indent=2),encoding="utf-8")
    state_tmp.replace(state_path)

    esc=lambda x:html.escape(str(x or ""),quote=True)
    page=['<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar free daily watch</title>',
          '<style>body{font:15px Segoe UI,Arial;max-width:1050px;margin:32px auto;padding:0 18px;color:#263244;background:#f5f7fa}',
          'article{background:white;border:1px solid #dde4ee;border-radius:9px;margin:14px 0;padding:17px}',
          'small{color:#526171}a{color:#145da2}</style></head><body>',
          '<h1>GTA Radar — Free public-data early warning</h1>',
          '<p><b>Public records checked:</b> '+str(len(full))+
          ' · <b>First observed after baseline:</b> '+str(count["FIRST_OBSERVED"])+
          ' · <b>Records changed:</b> '+str(count["RECORD_CHANGED"])+
          ' · <b>Initial baseline:</b> '+str(count["INITIAL_BASELINE"])+
          ' · <b>Previously archived regional records first indexed:</b> '+str(count["ARCHIVE_CONTEXT"])+
          '.</p>',
          '<p><b>DeepSeek calls: 0. Estimated DeepSeek cost: $0.</b> '
          'First seen is first observed by Radar, NOT municipal permit issue date. '
          'Status is a saved local source observation, NOT a current live verification. '
          'No supplier availability established.</p>',
          '<p><a href="'+CSV_NAME+'">Open only first-seen or changed records (CSV)</a> · '+
          '<a href="'+ALL_NAME+'">All public-source candidates for this run (CSV)</a></p>']
    if not active:
        page.append('<p>No first-seen or materially changed records since the previous baseline. '
                    'Collection still ran; all public-source candidates remain available above.</p>')
    for row in active:
        page.append('<article><h3>'+esc(row['address'] or row['project_id'])+
                    ' · '+esc(row['observation'].replace("_"," ").title())+'</h3>'+
                    '<p><b>Project:</b> '+esc(row['description'])+'</p>'+
                    '<p><b>Local status:</b> '+esc(row['current_source_status'] or "Not recorded")+
                    ' · <b>Stage:</b> '+esc(row['stage_from_local_status'])+
                    ' · <b>Source date:</b> '+esc(row['source_record_date'] or "Unknown")+
                    '</p><p><b>Possible services:</b> '+esc(row['service_hypotheses'])+
                    '</p><p>'+esc(row['follow_up'])+'</p>')
        url=row['record_source_url']
        if url and urlparse(url).scheme=="https" and urlparse(url).hostname:
            page.append('<a href="'+esc(url)+'" rel="noopener noreferrer">Official/source record lookup (verify current status)</a>')
        page.append('</article>')
    page.append('</body></html>')
    (out/HTML_NAME).write_text(''.join(page),encoding="utf-8")
    return dict(first_observed=count["FIRST_OBSERVED"],record_changed=count["RECORD_CHANGED"],
                initial_baseline=count["INITIAL_BASELINE"],
                archive_context=count["ARCHIVE_CONTEXT"],
                total_records=len(full),new_or_changed=len(active),
                report=HTML_NAME,csv=CSV_NAME,ai_calls=0,deepseek_cost_usd=0)
