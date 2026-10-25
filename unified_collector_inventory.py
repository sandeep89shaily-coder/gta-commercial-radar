"""Single consolidated collector inventory for V8, including review-only pilots.

Only observes current pipeline outcomes. Never runs sources or incurs AI charges.
"""
import csv
import json
from pathlib import Path

REVIEW_ONLY={
    "early_ajax":"Ajax post-baseline changes reach common engine only when commercial use is corroborated",
    "early_markham":"Markham reports are index-only, not confirmed projects",
    "early_investment_tenders":"Public tenders/investment news require location and buyer qualification",
}
FIELDS=("source_id","group","execution_status","integration_status","reason")

def build(results, config, steps):
    output=Path(results)/"GTA_RADAR_ALL_SOURCE_STATUS.csv"
    source_defs=json.loads(Path(config).read_text(encoding="utf-8"))
    rows=[]
    for source in source_defs:
        active=bool(source.get("enabled",False))
        rows.append(dict(source_id=source["id"],group="CORE_CONFIG",
            execution_status="CONFIGURED_ENABLED" if active else "CONFIGURED_DISABLED",
            integration_status="CORE_ENGINE" if active else "NOT_ENABLED",
            reason="" if active else "Awaiting safe feed-specific activation"))
    for step in steps:
        name=step.get("step","")
        if not name.startswith("early_"):continue
        reason=REVIEW_ONLY.get(name,"")
        rows.append(dict(source_id=name,group="INDEPENDENT_COLLECTOR",
            execution_status=step.get("status","UNKNOWN"),
            integration_status="REVIEW_ONLY" if reason else "EARLY_CHANGE_BRIDGE",
            reason=reason))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    return output,{"inventory_count":len(rows),
        "disabled_count":sum(r["integration_status"]=="NOT_ENABLED" for r in rows),
        "review_only_pilots":sum(r["integration_status"]=="REVIEW_ONLY" for r in rows)}
