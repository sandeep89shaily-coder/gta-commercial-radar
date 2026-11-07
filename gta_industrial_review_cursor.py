"""Persistent, source-preserving review cursor for the manual industrial pilot.

Kept OUTSIDE the production radar.sqlite. Read the previous status once to seed
successful visits from older pilot versions, then move through distinct notices.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path

LEDGER = "GTA_RADAR_ERO_REVIEW_CURSOR.json"
PREVIOUS_STATUS = "GTA_RADAR_INDUSTRIAL_EQUIPMENT_STATUS.json"

def _read(path):
    try:
        obj=json.loads(Path(path).read_text(encoding="utf-8"))
        return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError,TypeError):
        return {}

def fingerprint(card):
    """Only source publication/status changes requalify already parsed notices."""
    return "|".join(str(card.get(f,"") or "").strip().casefold()
                    for f in ("notice_stage","last_updated","proposal_posted"))

def load(out,cards):
    out=Path(out)
    state=_read(out/LEDGER)
    if state.get("version")==1 and isinstance(state.get("notices"),dict):
        return state
    history={"version":1,"notices":{}}
    # Migrates the user's successful third pilot: those five ERO pages were
    # already reviewed, even though older code lacked a persistent cursor.
    previous=_read(out/PREVIOUS_STATUS)
    for record in previous.get("official_fetch_audit",[]):
        no=str(record.get("ero_number") or "")
        if record.get("status")!="DETAIL_RETRIEVED" or no not in cards:
            continue
        history["notices"][no]={
            "status":"DETAIL_RETRIEVED",
            "card_fingerprint":fingerprint(cards[no]),
            "migrated_from_previous_status":True,
        }
    return history

def select(cards,state,limit):
    limit=max(0,min(int(limit),10))
    seen=state.get("notices",{})
    changed=[];new=[];retry=[]
    for no in sorted(cards,reverse=True):
        old=seen.get(no)
        if old and old.get("status")=="DETAIL_RETRIEVED":
            if old.get("card_fingerprint")!=fingerprint(cards[no]):
                changed.append(no)
        elif old:
            retry.append(no)
        else:
            new.append(no)
    ids=(changed+new+retry)[:limit]
    return {no:cards[no] for no in ids}

def update(state,cards,audit):
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    for record in audit:
        no=record.get("ero_number")
        if no not in cards:
            continue
        if record.get("status") not in {
            "DETAIL_RETRIEVED","DETAIL_REJECTED","ROBOTS_DISALLOW_NOTICE"
        }:
            continue
        state.setdefault("notices",{})[no]={
            "status":record["status"],
            "card_fingerprint":fingerprint(cards[no]),
            "last_attempt_utc":now,
            "failure_reason":record.get("reason","")[:160],
        }
    return state

def save(out,state):
    target=Path(out)/LEDGER
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(".tmp")
    tmp.write_text(json.dumps(state,indent=2,sort_keys=True),encoding="utf-8")
    tmp.replace(target)

def reviewed_count(state):
    return sum(v.get("status")=="DETAIL_RETRIEVED"
               for v in state.get("notices",{}).values())
