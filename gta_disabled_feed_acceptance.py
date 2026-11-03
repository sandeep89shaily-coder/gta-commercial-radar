"""Staged GIS source audit. No credential, AI, forced access, or automatic activation."""
from __future__ import annotations
import argparse,datetime as dt,json,socket
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urlparse
import requests
from robots_policy import evaluate
from toronto_pdf_download import public_dns

ROOT=Path(__file__).resolve().parent
AGENT="GTARadarStagedSourceAudit/1.0"
def field_matches(config,names):
    present={n.upper() for n in names}
    return {category:[x for x in config.get(config_key,[]) if x.upper() in present]
        for category,config_key in (
            ("identity","key_fields"),("scope","description_fields"),("dates","date_fields"))}

def fetch(ss,url,params=None):
    p=urlparse(url)
    if (p.scheme!="https" or not p.hostname or p.username or p.password
        or p.port not in (None,443) or p.fragment
        or not public_dns(p.hostname,socket.getaddrinfo)):
        raise ValueError("NON_PUBLIC_SOURCE")
    allowed,reason=evaluate(ss,url,AGENT,timeout=7)
    if not allowed:raise ValueError("POLICY_BLOCKED:"+str(reason))
    with ss.get(url,params=params or {},timeout=(6,14),stream=True,allow_redirects=False) as r:
        if r.status_code!=200 or urlparse(r.url).hostname!=p.hostname:
            raise ValueError("HTTP_"+str(r.status_code)+"_OR_REDIRECT")
        raw=bytearray()
        for chunk in r.iter_content(65536):
            raw.extend(chunk)
            if len(raw)>1500000:raise ValueError("EXCESSIVE_BODY")
        j=json.loads(raw)
        if not isinstance(j,dict) or j.get("error"):
            raise ValueError("SOURCE_API_ERROR:"+str(j.get("error"))[:120])
        return j

def probe(s):
    row={"id":s["id"],"name":s["name"],"mode":s.get("mode"),
         "status":"NOT_TESTED","safe_to_stage":False}
    if s.get("collector")!="arcgis":
        row["status"]="HISTORICAL_BACKFILL_NOT_DAILY";return row
    ss=requests.Session();ss.trust_env=False
    ss.headers.update({"User-Agent":AGENT,"Accept":"application/json"})
    try:
        meta=fetch(ss,s["url"],{"f":"json"})
        names=[v.get("name","") for v in meta.get("fields",[]) if isinstance(v,dict)]
        if not names:raise ValueError("NO_LAYER_SCHEMA")
        matches=field_matches(s,names)
        row.update(fields=matches,field_count=len(names),
                   layer_name=meta.get("name",""))
        if not matches["identity"]:
            row["status"]="NO_CONFIGURED_IDENTITY_FIELD";return row
        query=s.get("query_url",s["url"].rstrip("/")+"/query")
        chosen=matches["identity"][:2]+matches["scope"][:1]+matches["dates"][:1]
        result=fetch(ss,query,{"f":"json","where":"1=1",
            "outFields":",".join(chosen),"returnGeometry":"false",
            "resultRecordCount":"1"})
        features=result.get("features")
        if not isinstance(features,list):raise ValueError("NO_FEATURE_LIST")
        row["records_checked"]=len(features)
        row["sample_identity_valid"]=bool(features and any(
            str(features[0].get("attributes",{}).get(k,"")).strip()
            for k in matches["identity"]))
        row["safe_to_stage"]=bool(row["sample_identity_valid"] and matches["scope"])
        row["status"]=("PROBE_OK_NEEDS_BASELINE_AND_LICENCE" if row["safe_to_stage"]
                       else "MISSING_SCOPE_OR_IDENTITY")
    except Exception as exc:
        row["status"]="ROBOTS_BLOCKED" if "POLICY_BLOCKED" in str(exc) else "FETCH_OR_SCHEMA_FAILED"
        row["error"]=type(exc).__name__+":"+str(exc)[:180]
    finally:ss.close()
    return row

def run(output,config=None,worker=probe):
    data=config if config is not None else json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
    disabled=[x for x in data if not x.get("enabled")]
    rows=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={pool.submit(worker,x):x["id"] for x in disabled}
        for future in as_completed(futures):
            try:row=future.result()
            except Exception as exc:row={"id":futures[future],"status":"AUDITOR_ERROR","error":str(exc)[:150]}
            rows.append(row)
            print("STAGED_SOURCE",json.dumps(row),flush=True)
    rows.sort(key=lambda x:x["id"])
    report={"generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "disabled_count":len(disabled),
        "safe_to_stage_count":sum(bool(r.get("safe_to_stage")) for r in rows),
        "blocked_count":sum(r["status"]=="ROBOTS_BLOCKED" for r in rows),
        "sources":rows,
        "warning":"A one-record probe does not confirm comprehensive collection, first-seen correctness, or resale rights."}
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/"DISABLED_FEEDS_SOURCE_ACCEPTANCE.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    args=p.parse_args()
    result=run(args.output)
    print("DISABLED_FEED_TOTAL",json.dumps({k:result[k] for k in ("disabled_count","safe_to_stage_count","blocked_count")}))
