"""Read-only date-field diagnostics for five disabled sources; no project content saved."""
import csv
import json
from datetime import datetime,timezone
from pathlib import Path
import requests

IDS={"hamilton_development_applications","kitchener_active_planning_applications",
"durham_planit_consents","durham_planit_opa","durham_business_sites"}
FIELDS=("source_id","checked_utc","metadata_status","configured_dates",
"candidate_date_fields","sample_nonnull_counts","sample_size","caveat","error")
def inspect(source,session=None):
    row=dict(source_id=source["id"],checked_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        metadata_status="UNVERIFIED",configured_dates=";".join(source.get("date_fields",[])),
        candidate_date_fields="",sample_nonnull_counts="",sample_size=0,
        caveat="Metadata/type and 3-row sample cannot establish source publishing date",error="")
    try:
        session=session or requests.Session()
        response=session.get(source["url"],params={"f":"json"},timeout=(8,20))
        response.raise_for_status()
        if len(response.content)>2_000_000:raise ValueError("metadata cap exceeded")
        metadata=response.json()
        if metadata.get("error"):raise ValueError("ArcGIS metadata error")
        candidates=[f["name"] for f in metadata.get("fields",[]) if
            f.get("type")=="esriFieldTypeDate" or
            any(token in f.get("name","").lower() for token in ("date","modified","updated","created","received","submitted"))]
        row["candidate_date_fields"]=";".join(candidates[:40])
        if not candidates:
            row["metadata_status"]="NO_DATE_CANDIDATES"
            return row
        response=session.get(source["url"].rstrip("/")+"/query",
            params={"f":"json","where":"1=1","outFields":",".join(candidates[:20]),
                    "returnGeometry":"false","resultRecordCount":3},timeout=(8,20))
        response.raise_for_status()
        if len(response.content)>200_000:raise ValueError("sample cap exceeded")
        data=response.json()
        if data.get("error") or not isinstance(data.get("features"),list):
            raise ValueError("ArcGIS sample query error")
        samples=[x.get("attributes",{}) for x in data["features"]]
        row["sample_size"]=len(samples)
        row["sample_nonnull_counts"]=";".join(f"{name}:{sum(a.get(name) is not None and a.get(name)!='' for a in samples)}"
                                             for name in candidates[:20])
        row["metadata_status"]="DATE_CANDIDATES_SAMPLED" if samples else "EMPTY_SAMPLE"
    except (requests.RequestException,ValueError,TypeError,KeyError) as exc:
        row["error"]=(type(exc).__name__+": "+str(exc))[:180]
    return row
def run(config="config/sources.json",output="date-audit/DISABLED_SOURCE_DATE_GAPS.csv",session=None):
    sources=json.loads(Path(config).read_text(encoding="utf-8"))
    rows=[inspect(s,session=session) for s in sources if s["id"] in IDS and not s.get("enabled")]
    dst=Path(output);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    for r in rows:print(r["source_id"],r["metadata_status"],r["candidate_date_fields"],
                         r["sample_nonnull_counts"],r["error"])
    return rows
if __name__=="__main__":run()
