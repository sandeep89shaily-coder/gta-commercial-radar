"""Promote existing Southern Ontario permits/planning without fabricating fresh events.

The usual 48-hour change export is Toronto-heavy. This read-only bridge adds
bounded, source-dated existing public projects by jurisdiction from the Radar
SQLite archive and reports sources without usable records. Never backdate or
call older baselines NEW. Does not enable untested/licence-uncleared feeds.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

from official_record_verifier import SOURCES

VALID_REGIONS={"Peel","Toronto","York","Halton","Durham","Hamilton","Waterloo","Niagara"}
PRIORITY={"Peel":0,"York":1,"Halton":2,"Durham":3,"Hamilton":4,"Waterloo":5,"Niagara":6,"Toronto":7}
FIELDS=["source_id","source_key","source_group","description","address","city",
        "company_name","event_date","event_date_basis","evidence_url"]
STATS=["source_id","jurisdiction","region","configured_enabled","records_in_database",
       "eligible_source_dated_records","selected_for_research","reason"]
IGNORED={"health_inspection","permit_history"}

def _date(value):
    raw=str(value or "").strip()
    try:return dt.date.fromisoformat(raw[:10])
    except ValueError:return None

def _age_ok(raw,when,max_days):
    d=_date(raw)
    return bool(d and 0<=(when-d).days<=max_days)

def _write(path,fields,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as file:
        w=csv.DictWriter(file,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def bridge(database,output_dir,*,today=None,max_days=180,per_source=18,per_region=50):
    """Read-only balanced regional supplement + honest coverage inventory.

    Records are NOT relabeled as "new" simply because imported recently.
    Existing V4 grouping and commercial filtering still apply afterward.
    """
    database=Path(database)
    today=today or dt.date.today()
    by_source={s["id"]:s for s in SOURCES
               if s.get("region") in VALID_REGIONS
               and s.get("family") in ("permit","planning_application","industrial_regulatory")}
    db_counts=defaultdict(int);eligible=defaultdict(int);pool=defaultdict(list)
    if database.is_file():
        with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True)) as con:
            try:
                rows=con.execute(
                    "SELECT source_id,record_key,source_date,normalized_json "
                    "FROM records_current WHERE active=1 "
                    "AND source_date IS NOT NULL AND source_date<>'' "
                    "ORDER BY source_date DESC"
                )
                for sid,key,date,raw in rows:
                    if sid not in by_source:continue
                    db_counts[sid]+=1
                    if not _age_ok(date,today,max_days):continue
                    try:d=json.loads(raw)
                    except (ValueError,TypeError):continue
                    if not isinstance(d,dict) or d.get("commercial_relevance")=="LOW":
                        continue
                    desc=str(d.get("description") or "").strip()
                    address=str(d.get("address") or "").strip()
                    if not desc or not address or not key:continue
                    eligible[sid]+=1
                    if len(pool[sid])<per_source:
                        pool[sid].append((date,str(key),d))
            except sqlite3.Error:
                # The old database is not mutated, and no empty-success
                # assertion is made if the expected schema is missing.
                raise

    candidates=[];regional_counts=defaultdict(int);source_counts=defaultdict(int)
    for sid in sorted(pool,key=lambda x:(PRIORITY.get(by_source[x]["region"],99),x)):
        s=by_source[sid];region=s["region"]
        for date,key,d in pool[sid]:
            if regional_counts[region]>=per_region or source_counts[sid]>=per_source:break
            row=dict(source_id=sid,source_key=key,source_group="REGIONAL_ARCHIVED_SOURCE",
                     description=str(d.get("description") or "")[:2200],
                     address=str(d.get("address") or ""),
                     city=str(s.get("jurisdiction") or ""),
                     company_name=str(d.get("entity_name") or ""),
                     event_date=date,
                     event_date_basis="EXISTING_PUBLISHED_SOURCE_DATE_NOT_NEW_EVENT",
                     evidence_url=str(d.get("evidence_url") or ""))
            candidates.append(row);source_counts[sid]+=1;regional_counts[region]+=1
    stats=[]
    for sid,s in sorted(by_source.items(),key=lambda x:(PRIORITY.get(x[1]["region"],99),x[0])):
        if source_counts[sid]:
            label="SOURCE_DATED_RESEARCH_CANDIDATES"
        elif not s.get("enabled"):
            label="STAGED_DISABLED_NOT_COLLECTED_OR_NO_DATED_RECORDS"
        elif db_counts[sid]==0:
            label="NO_ACTIVE_SOURCE_RECORDS_IN_LOCAL_DATABASE"
        elif eligible[sid]==0:
            label="NO_RECENT_SOURCE_DATED_COMMERCIAL_RECORDS"
        else:
            label="PER_REGION_OR_SOURCE_CAP"
        stats.append(dict(source_id=sid,jurisdiction=s.get("jurisdiction",""),
                          region=s.get("region",""),
                          configured_enabled=str(bool(s.get("enabled"))),
                          records_in_database=db_counts[sid],
                          eligible_source_dated_records=eligible[sid],
                          selected_for_research=source_counts[sid],
                          reason=label))
    out=Path(output_dir)
    _write(out/"GTA_RADAR_REGIONAL_SOURCE_CANDIDATES.csv",FIELDS,candidates)
    _write(out/"GTA_RADAR_REGIONAL_COVERAGE.csv",STATS,stats)
    return candidates,stats


def selection_input(base_csv, database, output, today=None):
    """Union 48-hour events and balanced sourced regional inventory for V4.

    Never overwrite the collector's 48h source file. Dedupe by the pair of
    source ID and exact published record key, not by address.
    """
    base=Path(base_csv);out=Path(output)
    regional,inventory=bridge(database,out,today=today)
    with base.open(encoding="utf-8-sig",newline="") as f:
        current=list(csv.DictReader(f))
    seen=set();combined=[]
    for r in current+regional:
        key=(str(r.get("source_id") or ""),str(r.get("source_key") or ""))
        if not all(key) or key in seen:continue
        seen.add(key);combined.append(r)
    fields=list(dict.fromkeys([k for r in combined for k in r] + FIELDS))
    _write(out/"GTA_RADAR_COMBINED_SELECTION_INPUT.csv",fields,combined)
    original=len({(str(r.get("source_id") or ""),str(r.get("source_key") or ""))
                  for r in current if r.get("source_id") and r.get("source_key")})
    return out/"GTA_RADAR_COMBINED_SELECTION_INPUT.csv",{
        "regional_source_records_added":max(0,len(combined)-original),
        "regional_source_records_considered":len(regional),
        "regional_regions_represented":sorted({r["region"] for r in inventory
                                               if r["selected_for_research"]}),
        "staged_sources_not_enabled":sum(r["reason"].startswith("STAGED_DISABLED") for r in inventory),
        "regional_sources_with_projects":sum(bool(r["selected_for_research"]) for r in inventory),
    }
