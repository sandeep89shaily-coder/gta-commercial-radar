"""Conservative monthly Durham official open-data staging.

Four sources passed real policy, schema and one-row probes. Fetches complete
bounded snapshots, first-success baselines and changes in independent source
ledgers. Does NOT enter sales lead pipelines. Never bypasses robots policy.
"""
from __future__ import annotations
import csv,datetime as dt,hashlib,json,re
from pathlib import Path
from gta_disabled_feed_acceptance import fetch,field_matches,ROOT,AGENT
import requests

SELECTED=("durham_planit_consents","durham_planit_opa",
          "durham_business_sites","durham_capital_projects")
STATE="GTA_RADAR_STAGED_DURHAM_SEEN.json"
STATUS="GTA_RADAR_STAGED_DURHAM_STATUS.json"
ALL="GTA_RADAR_STAGED_DURHAM_EVIDENCE.csv"
CHANGED="GTA_RADAR_STAGED_DURHAM_CHANGED_REVIEW.csv"
FIELDS=("source_id","record_id","jurisdiction","project_description",
        "source_record_date","status","address","source_url",
        "observation","first_seen_local","record_kind","verification_required")
LIMIT=10000
PAGE=250

def _clean(x):
    if x is None:return ""
    return re.sub(r"\s+"," ",str(x)).strip()[:900]

def _collect(source,fetcher):
    meta=fetcher(source["url"],{"f":"json"})
    schema=[f.get("name","") for f in meta.get("fields",[]) if isinstance(f,dict)]
    fields=field_matches(source,schema)
    if not fields["identity"] or not fields["scope"]:
        raise ValueError("SOURCE_SCHEMA_ID_OR_DESCRIPTION_MISSING")
    have={n.upper():n for n in schema}
    def choose(candidates):
        return [have[n.upper()] for n in candidates if n.upper() in have]
    ids=fields["identity"]
    scope=fields["scope"]
    dates=fields["dates"]
    addresses=choose(source.get("address_fields",[]))
    statuses=choose(source.get("status_fields",[]))
    order=meta.get("objectIdField") or next((x for x in schema if x.upper()=="OBJECTID"),None)
    query=source.get("query_url") or source["url"].rstrip("/")+"/query"
    count=fetcher(query,{"f":"json","where":"1=1","returnCountOnly":"true"}).get("count")
    if not isinstance(count,int) or count<0 or count>LIMIT:
        raise ValueError("UNSAFE_OR_MISSING_SOURCE_COUNT:"+str(count))
    if count and not order:raise ValueError("STABLE_SORT_REQUIRED")
    names=list(dict.fromkeys(ids+scope+dates+addresses+statuses+([order] if order else [])))
    if count==0:return [],fields
    collected=[];offset=0
    while offset<count:
        params={"f":"json","where":"1=1","returnGeometry":"false",
                "outFields":",".join(names),"resultOffset":str(offset),
                "resultRecordCount":str(min(PAGE,count-offset)),
                "orderByFields":order+" ASC"}
        result=fetcher(query,params)
        features=result.get("features")
        if not isinstance(features,list) or not features:
            raise ValueError("EMPTY_OR_INVALID_PAGE_BEFORE_COUNT")
        for feature in features:
            attrs=feature.get("attributes",{}) if isinstance(feature,dict) else {}
            identity=next((_clean(attrs.get(k)) for k in ids if _clean(attrs.get(k))),"")
            if not identity:raise ValueError("MISSING_ROW_IDENTITY")
            desc=" | ".join(_clean(attrs.get(k)) for k in scope if _clean(attrs.get(k)))
            if not desc:continue
            date=next((_clean(attrs.get(k)) for k in dates if _clean(attrs.get(k))),"")
            address=next((_clean(attrs.get(k)) for k in addresses if _clean(attrs.get(k))),"")
            status=next((_clean(attrs.get(k)) for k in statuses if _clean(attrs.get(k))),"")
            collected.append({"source_id":source["id"],
                "record_id":identity,"jurisdiction":source.get("jurisdiction","Durham"),
                "project_description":desc,"source_record_date":date,
                "status":status,"address":address,
                "source_url":source["url"],
                "record_kind":"REFERENCE_OR_PLANNING_RECORD_NOT_SALES_READY",
                "verification_required":"Verify scope, file identity, timing, status and purchasing relevance"})
        offset+=len(features)
        if len(features)>PAGE or offset>count:
            raise ValueError("INCONSISTENT_PAGE_LENGTH")
    if offset!=count:raise ValueError("PARTIAL_SOURCE_SNAPSHOT")
    keys=[(r["source_id"],r["record_id"]) for r in collected]
    if len(keys)!=len(set(keys)):raise ValueError("NON_UNIQUE_IDENTIFIERS")
    return collected,fields

def _csv(path,rows):
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader();w.writerows(rows)

def run(results,*,today=None,sources=None,fetcher=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    cfg=sources if sources is not None else json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
    selected={s["id"]:s for s in cfg if s["id"] in SELECTED}
    if set(selected)!=set(SELECTED):raise ValueError("MISSING_DURHAM_SOURCE_CONFIG")
    ledger=root/STATE
    state=json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"schema":1,"sources":{}}
    if state.get("schema")!=1:raise ValueError("UNKNOWN_SOURCE_STATE_SCHEMA")
    allrows=[];new=[];results_status=[]
    # Retain prior successful evidence when a source is skipped by its monthly
    # cadence or becomes inaccessible; never report it as newly fetched.
    old_rows={}
    if (root/ALL).exists():
        with (root/ALL).open(encoding="utf-8-sig",newline="") as handle:
            for row in csv.DictReader(handle):
                old_rows.setdefault(row.get("source_id",""),[]).append(row)
    ss=requests.Session();ss.trust_env=False
    ss.headers["User-Agent"]=AGENT
    reader=fetcher or (lambda url,params:fetch(ss,url,params))
    for sid in SELECTED:
        src=selected[sid]
        old=state["sources"].get(sid)
        # This feed is deliberately monthly; skip untouched same-month baselines.
        if old and old.get("last_success_month")==day[:7]:
            allrows.extend(old_rows.get(sid,[]))
            results_status.append({"source_id":sid,"status":"SKIPPED_MONTHLY_CADENCE",
                                   "retained_previous_rows":len(old_rows.get(sid,[])),
                                   "baseline_preserved":True});continue
        try:
            records,fields=_collect(src,reader)
            prior=old.get("seen",{}) if old else {}
            updated=dict(prior)
            for row in records:
                key=row["record_id"]
                digest=hashlib.sha256(json.dumps({k:row[k] for k in ("project_description",
                       "source_record_date","status","address")},sort_keys=True).encode()).hexdigest()
                prev=prior.get(key)
                observation=("INITIAL_BASELINE" if old is None else
                    "FIRST_OBSERVED" if prev is None else
                    "RECORD_CHANGED" if prev["digest"]!=digest else "UNCHANGED")
                row["observation"]=observation
                row["first_seen_local"]=prev["first_seen_local"] if prev else day
                allrows.append(row)
                if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):new.append(row)
                updated[key]={"digest":digest,"first_seen_local":row["first_seen_local"]}
            state["sources"][sid]={"seen":updated,"last_success_month":day[:7],
                "baseline_date":old.get("baseline_date",day) if old else day}
            results_status.append({"source_id":sid,"status":"BASELINED" if old is None else "COLLECTED",
                "source_records":len(records),"changed":sum(r["source_id"]==sid for r in new),
                "fields":fields,"baseline_preserved":False})
        except Exception as exc:
            allrows.extend(old_rows.get(sid,[]))
            results_status.append({"source_id":sid,"status":"FAILED",
                "error":type(exc).__name__+":"+str(exc)[:180],
                "retained_previous_rows":len(old_rows.get(sid,[])),
                "baseline_preserved":True})
    ss.close()
    # Successful source baselines are persisted independently of failures.
    temp=ledger.with_suffix(".tmp")
    temp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    temp.replace(ledger)
    _csv(root/ALL,allrows);_csv(root/CHANGED,new)
    result={"sources":results_status,"total_rows":len(allrows),
        "new_or_changed_reference_records":len(new),"paid_ai_calls":0,
        "sales_lead_publication":False,
        "warning":"Evidence-only monthly staging. Historical first successful fetch is baseline; sources need commercial scope verification."}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
