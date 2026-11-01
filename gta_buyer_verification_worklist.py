"""Prioritized follow-up queue for evidence-backed, not-yet-verified buyer relationships."""
from __future__ import annotations
import csv,json
from gta_verified_source_pipeline import classify_buyer
from pathlib import Path
from gta_live_procurement_evidence import _source_project_index
import reviewed_evidence

FIELDS=("organization","role","project_id","source_url","exact_quote","buyer_authority_status",
        "supplier_selection_status","contact_route_status","next_evidence_required")

def build(folder):
    folder=Path(folder); source=folder/"BUYER_RELATIONSHIPS_REVIEW.json"
    try:data=json.loads(source.read_text(encoding="utf-8"))
    except (OSError,ValueError):data={}
    projects=_source_project_index(folder)
    rows=[]
    for item in data.get("observations",[]):
        if not item.get("source_url") or not item.get("exact_quote"):
            continue
        role=str(item.get("role") or "UNKNOWN").lower()
        needed=("Public evidence that the organization controls purchasing; "
                "official contact route; supplier/contract award status")
        if role in ("architect","agent"):
            needed="Establish owner/developer/operator and purchasing authority; agent is not buyer"
        evidence=classify_buyer(item)
        rows.append(dict(organization=item.get("organization",""),role=role,
                         project_id=(str(item.get("project_id") or "").strip() or
                           (next(iter(projects[item["source_url"]]))
                            if len(projects.get(item["source_url"],set()))==1 else "")),
                         source_url=item["source_url"],exact_quote=item["exact_quote"],
                         buyer_authority_status=evidence["buyer_authority"],
                         supplier_selection_status=evidence["supplier_status"],
                         contact_route_status="NOT_VERIFIED",
                         next_evidence_required=needed))
    with (folder/"BUYER_VERIFICATION_WORKLIST.csv").open("w",newline="",encoding="utf-8-sig") as out:
        writer=csv.DictWriter(out,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    gate=reviewed_evidence.evaluate_folder(folder)["results"].values()
    result={"candidates_for_human_or_official_source_verification":len(rows),
            "verified_buyers":sum(g["buyer_authority_verified"] for g in gate),
            "unawarded_supplier_packages_verified":sum(g["supplier_selection_verified"] for g in gate),
            "status":"REVIEW_REQUIRED" if rows else "NO_SOURCE_BACKED_BUYER_CANDIDATES"}
    (folder/"BUYER_VERIFICATION_WORKLIST_STATUS.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True)
    print(json.dumps(build(p.parse_args().folder),indent=2))
