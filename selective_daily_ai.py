"""Selectively buy DeepSeek research for real first-seen or changed projects.

Separate small persistent pending file survives a 48-hour collector window and
does not empty or reprice the historical V8 research queue. Does not call any AI
unless an eligible original municipal/commercial source event exists.
"""
from __future__ import annotations
import csv
import datetime as dt
import re
from pathlib import Path

from commercial_selector_v4 import (ACTION, COMMERCIAL, SMALL_RESIDENTIAL,
                                    RESIDENTIAL_LED, INDEPENDENT_COMMERCIAL,
                                    NO_WORK)
from opportunity_lifecycle import classify_status
import v8_ai_queue as queue

CAP_USD=0.25
PENDING="GTA_RADAR_SELECTIVE_AI_PENDING.csv"
HISTORY="GTA_RADAR_V8_INVESTIGATIONS.csv"
MIN_PRIORITY=35
STAGES_BLOCKED={"COMPLETED","BLOCKED_OR_INACTIVE","INSPECTION_STAGE"}

def read(path):
    p=Path(path)
    if not p.is_file():return []
    with p.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def permitted(row):
    """Rules cost nothing. A named building without actual new work is not enough."""
    lane=str(row.get("lane") or "")
    source=str(row.get("source_id") or "").lower()
    desc=str(row.get("description") or "")
    stage=classify_status(row.get("current_source_status"))
    if lane not in ("EARLY_SIGNAL_WATCH","PERMIT_REVIEW","PLANNING_WATCH","BUSINESS_REVIEW"):
        return False
    if "inspection" in source or "health_food" in source:
        return False
    if stage in STAGES_BLOCKED or NO_WORK.search(desc):
        return False
    early_planning=(lane in ("EARLY_SIGNAL_WATCH","PLANNING_WATCH") and bool(
        re.search(r"\b(site[\s-]?plan|pre[ -]?consultation|propos\w*|"
                  r"planning application|new industrial|connection assessment|"
                  r"planned expansion)\b",desc,re.I)))
    if not desc or not COMMERCIAL.search(desc) or not (ACTION.search(desc) or early_planning):
        return False
    if (SMALL_RESIDENTIAL.search(desc) or RESIDENTIAL_LED.search(desc)) and not INDEPENDENT_COMMERCIAL.search(desc):
        return False
    if re.search(r"\b(?:temporary |fascia |awning )?sign(?:age)?\b",desc,re.I) and not re.search(
            r"\b(?:industrial|warehouse|factory|expansion|new building|tenant fit[\s-]?out)\b",desc,re.I):
        return False
    if not row.get("source_keys") and not row.get("project_id"):
        return False
    try:priority=int(row.get("review_priority") or 0)
    except ValueError:priority=0
    return priority>=MIN_PRIORITY

def enqueue(candidates_path,observations_path,results_dir):
    """Persist only fresh/changed commercial triggers, not the historic backlog."""
    root=Path(results_dir);root.mkdir(parents=True,exist_ok=True)
    observations={r.get("project_id"):r.get("observation")
                  for r in read(observations_path)
                  if r.get("observation") in ("FIRST_OBSERVED","RECORD_CHANGED")}
    fresh={r.get("project_id"):r for r in read(candidates_path) if r.get("project_id")}
    earlier={r["project_id"]:r for r in read(root/PENDING) if r.get("project_id")}
    newly=[]
    for pid,kind in observations.items():
        row=fresh.get(pid)
        if row is None or not permitted(row):
            continue
        previous=earlier.get(pid)
        if previous and queue.fingerprint(previous)==queue.fingerprint(row):
            continue
        earlier[pid]=row
        newly.append(pid)
    queue.save(root/PENDING,list(earlier.values()))
    return list(earlier.values()),newly

def prune(results_dir):
    """Mark one paid attempt per exact source fingerprint; don't pay it again.

    Unattempted budget-deferred rows persist and can be tried tomorrow.
    Already investigated same-fingerprint rows are removed regardless of
    provider outcome, avoiding repeat charges without material new source work.
    """
    root=Path(results_dir)
    old=read(root/PENDING)
    investigations={r.get("project_id"):r for r in read(root/HISTORY)}
    remaining=[]
    for row in old:
        prior=investigations.get(row.get("project_id"))
        same=prior and prior.get("input_fingerprint")==queue.fingerprint(row)
        if not (same and str(prior.get("api_attempted") or "").upper()=="YES"):
            remaining.append(row)
    queue.save(root/PENDING,remaining)
    return len(remaining)

def run(candidates_path,observations_path,results_dir,data_dir,*,today=None,
        transport=None,official_transport=None,max_runtime_seconds=600,key=None):
    root=Path(results_dir)
    queued,new_ids=enqueue(candidates_path,observations_path,root)
    # Old backlog is NOT eligible. This selection is *only* first-seen or
    # materially changed commercial records preserved in our small pending file.
    eligible={r["project_id"] for r in queued}
    result={"daily_ceiling_usd":CAP_USD,"new_eligible":len(new_ids),
            "pending_before":len(queued),"eligible_for_ai":len(eligible),
            "paid_research_attempts":0,"native_searches":0,
            "actual_daily_ledger_estimate_usd":0,"status":"NO_ELIGIBLE_NEW_PROJECTS"}
    if not eligible:
        return result
    import v8_deepseek_native as ai
    # Reuse existing source-wide input so updated projects enter the original
    # persistent V8 queue, but whitelist *only* these opted-in IDs as payable.
    r=ai.run(candidates_path,results_dir,legacy_data_dir=data_dir,
             today=today,transport=transport,official_transport=official_transport,
             max_runtime_seconds=max_runtime_seconds,key=key,
             budget_cap_usd=CAP_USD,eligible_project_ids=eligible)
    result.update(status=r.get("queue_stop_reason","UNKNOWN"),
                  paid_research_attempts=r.get("ai_calls_attempted",0),
                  native_searches=r.get("native_searches",0),
                  fetched_pages=r.get("native_fetches",0),
                  investigated=r.get("processed",0),
                  actual_daily_ledger_estimate_usd=r.get("reserved_usd",0),
                  company_contact_searches=r.get("company_contact_searches",0),
                  pending_after=prune(results_dir))
    return result
