"""Read-only ArcGIS metadata/schema audit for disabled Radar sources.

Does not enable feeds, fetch project rows, touch databases, or invoke DeepSeek.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests

COLUMNS = ("source_id","checked_at_utc","endpoint","http_status","schema_status",
           "missing_keys","missing_dates","field_count","error")

def probe(source, session=None):
    url = source.get("url", "").rstrip("/")
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = dict(source_id=source["id"],checked_at_utc=checked,endpoint=url,
               http_status="",schema_status="NOT_TESTED",missing_keys="",
               missing_dates="",field_count=0,error="")
    if source.get("collector") != "arcgis":
        row["schema_status"]="NOT_ARCGIS_REQUIRES_OTHER_PROBE"
        return row
    host=urlparse(url)
    if host.scheme!="https" or not host.hostname:
        row.update(schema_status="INVALID_ENDPOINT",error="HTTPS URL required")
        return row
    try:
        response=(session or requests.Session()).get(
            url,params={"f":"json"},timeout=(8,20),
            headers={"User-Agent":"GTA-Radar-Disabled-Source-Audit/1.0"})
        row["http_status"]=str(response.status_code)
        response.raise_for_status()
        if len(response.content)>3_000_000:raise ValueError("Oversize metadata response")
        body=response.json()
        if not isinstance(body,dict) or body.get("error"):
            raise ValueError("ArcGIS metadata error")
        fields={str(field.get("name","")).upper() for field in body.get("fields",[])
                if isinstance(field,dict)}
        if not fields:raise ValueError("No ArcGIS fields returned")
        missing_keys=[v for v in source.get("key_fields",[]) if v.upper() not in fields]
        missing_dates=[v for v in source.get("date_fields",[]) if v.upper() not in fields]
        row.update(field_count=len(fields),missing_keys=";".join(missing_keys),
                   missing_dates=";".join(missing_dates),
                   schema_status=("FIELDS_MATCH_CONFIG" if not missing_keys and not missing_dates
                                  else "CONFIG_FIELD_MISMATCH"))
    except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
        row.update(schema_status="UNVERIFIED_ENDPOINT",
                   error=(type(exc).__name__+": "+str(exc))[:200])
    return row

def audit(config="config/sources.json", output="GTA_RADAR_RESULTS/DISABLED_SOURCE_SCHEMA_AUDIT.csv",
          session=None):
    sources=json.loads(Path(config).read_text(encoding="utf-8"))
    disabled=[s for s in sources if not s.get("enabled")]
    rows=[probe(s,session=session) for s in disabled]
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("w",newline="",encoding="utf-8-sig") as file:
        writer=csv.DictWriter(file,fieldnames=COLUMNS);writer.writeheader();writer.writerows(rows)
    print(f"Disabled sources audited: {len(rows)}. No feeds enabled, no project records fetched.")
    for r in rows:print(r["source_id"],r["schema_status"],r["missing_keys"],r["missing_dates"])
    return rows

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",default="config/sources.json")
    parser.add_argument("--output",default="GTA_RADAR_RESULTS/DISABLED_SOURCE_SCHEMA_AUDIT.csv")
    args=parser.parse_args()
    audit(args.config,args.output)
