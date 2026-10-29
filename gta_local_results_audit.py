"""Audit an existing GTA_RADAR_RESULTS folder without changing production data."""
from __future__ import annotations
import csv,json,sqlite3
from pathlib import Path

def read_csv(path):
    if not path.exists():return None
    with path.open(encoding="utf-8-sig",newline="") as stream:
        rows=list(csv.DictReader(stream))
    return rows
def inspect(root):
    root=Path(root);issues=[]
    run=root/"GTA_RADAR_V6_RUN.json"
    state=json.loads(run.read_text(encoding="utf-8")) if run.exists() else {}
    results={"manifest_status":state.get("status","MISSING"),
             "manifest_started":state.get("started_local"),
             "source_logs":{},
             "counts":{},"gates":{}}
    for name in ("municipal_collector","business_collector","fresh_48h_opportunities"):
        log=root/"V6_LOGS"/(name+".log")
        results["source_logs"][name]={"present":log.exists(),"bytes":log.stat().st_size if log.exists() else 0}
    for name in ("GTA_RADAR_V8_PENDING_QUEUE","GTA_RADAR_V8_INVESTIGATIONS",
                 "GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST","GTA_RADAR_PUBLIC_COMPANY_CONTACTS"):
        rows=read_csv(root/(name+".csv"))
        results["counts"][name]=len(rows) if rows is not None else None
    investigations=read_csv(root/"GTA_RADAR_V8_INVESTIGATIONS.csv") or []
    results["gates"]["sale_ready"]=sum(str(r.get("sale_ready","")).strip().casefold()=="true" for r in investigations)
    results["gates"]["named_operator"]=sum(bool((r.get("operator") or "").strip()) for r in investigations)
    results["gates"]["named_developer"]=sum(bool((r.get("developer") or "").strip()) for r in investigations)
    results["gates"]["supplier_unknown"]=sum(r.get("supplier_contract_status","") in ("","NOT_ESTABLISHED","UNKNOWN") for r in investigations)
    bridge=root/"DOCUMENT_REVIEW"/"V8_BRIDGE_SUMMARY.json"
    if bridge.exists():
        results["document_bridge"]=json.loads(bridge.read_text(encoding="utf-8"))
    if state.get("status")=="RUNNING":issues.append("INCOMPLETE_V6_RUN_MANIFEST")
    if not results["gates"]["sale_ready"]:issues.append("NO_VERIFIED_SALE_READY_LEADS")
    if results["counts"]["GTA_RADAR_PUBLIC_COMPANY_CONTACTS"]==0:issues.append("NO_PUBLIC_COMPANY_CONTACT_EXPORT")
    results["issues"]=issues
    return results
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--results",required=True)
    a=p.parse_args();data=inspect(a.results)
    output=Path(a.results)/"GTA_RADAR_LOCAL_QUALITY_AUDIT.json"
    output.write_text(json.dumps(data,indent=2),encoding="utf-8")
    print(json.dumps(data,indent=2))
