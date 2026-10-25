"""Small read-only sample probe of disabled ArcGIS feeds.

Fetches at most 3 records per source; no storage of underlying project records,
no production/database writes, no DeepSeek, and no feed activation.
"""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
import requests

COLUMNS=("source_id","tested_at_utc","status","sample_count","stable_key_present",
         "date_field_present","sample_key_distinct","error")
def probe(source,session=None):
    checked=datetime.now(timezone.utc).isoformat(timespec="seconds")
    result=dict(source_id=source["id"],tested_at_utc=checked,status="NOT_CHECKED",
                sample_count=0,stable_key_present="UNKNOWN",date_field_present="UNKNOWN",
                sample_key_distinct="UNKNOWN",error="")
    if source.get("collector")!="arcgis":
        result["status"]="NOT_ARCGIS"
        return result
    url=source.get("query_url") or source.get("url","").rstrip("/")+"/query"
    parsed=urlparse(url)
    if parsed.scheme!="https" or not parsed.hostname:
        result.update(status="INVALID_URL",error="HTTPS required")
        return result
    try:
        response=(session or requests.Session()).get(url,params={
            "f":"json","where":"1=1","outFields":"*","returnGeometry":"false",
            "resultRecordCount":3},timeout=(8,20),
            headers={"User-Agent":"GTA-Radar-ReadOnly-Record-Sampler/1.0"})
        response.raise_for_status()
        if len(response.content)>800_000:raise ValueError("Response exceeded cap")
        payload=response.json()
        if not isinstance(payload,dict) or payload.get("error"):raise ValueError("ArcGIS query error")
        features=payload.get("features")
        if not isinstance(features,list):raise ValueError("Missing features list")
        result["sample_count"]=len(features)
        if not features:
            result["status"]="EMPTY_SAMPLE_NOT_VALIDATED"
            return result
        keys=source.get("key_fields",[])
        dates=source.get("date_fields",[])
        attrs=[f.get("attributes",{}) for f in features]
        values=[tuple(str(a.get(k) or "").strip() for k in keys) for a in attrs]
        present=bool(keys) and all(any(v for v in key) for key in values)
        result["stable_key_present"]=str(present)
        result["sample_key_distinct"]=str(present and len(set(values))==len(values))
        result["date_field_present"]=str(any(any(a.get(k) is not None for k in dates) for a in attrs)) if dates else "NO_CONFIGURED_DATE"
        result["status"]="SAMPLE_KEYS_PRESENT" if present and len(set(values))==len(values) else "KEY_QUALITY_REVIEW"
    except (requests.RequestException,ValueError,TypeError,AttributeError) as exc:
        result.update(status="UNVERIFIED_QUERY",error=(type(exc).__name__+": "+str(exc))[:180])
    return result

def audit(config="config/sources.json",output="GTA_RADAR_RESULTS/DISABLED_SOURCE_SAMPLE_AUDIT.csv",session=None):
    sources=json.loads(Path(config).read_text(encoding="utf-8"))
    rows=[probe(s,session=session) for s in sources if not s.get("enabled")]
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=COLUMNS);writer.writeheader();writer.writerows(rows)
    print("Review-only source sample results; no source enabled or DeepSeek used")
    for r in rows:print(r["source_id"],r["status"],r["sample_count"],r["stable_key_present"],r["date_field_present"],r["error"])
    return rows

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--config",default="config/sources.json")
    p.add_argument("--output",default="GTA_RADAR_RESULTS/DISABLED_SOURCE_SAMPLE_AUDIT.csv")
    a=p.parse_args();audit(a.config,a.output)
