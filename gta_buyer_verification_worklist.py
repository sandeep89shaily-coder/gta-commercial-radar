"""Prioritized follow-up queue for evidence-backed, not-yet-verified buyer relationships."""
from __future__ import annotations
import csv,json
from pathlib import Path

FIELDS=("organization","role","project_id","source_url","exact_quote","buyer_authority_status",
        "supplier_selection_status","contact_route_status","next_evidence_required")

def build(folder):
    folder=Path(folder); source=folder/"BUYER_RELATIONSHIPS_REVIEW.json"
    try:data=json.loads(source.read_text(encoding="utf-8"))
    except (OSError,ValueError):data={}
    projects={}
    for f in folder.glob("AI_PROJECT_????????????????.json"):
        try:
            obj=json.loads(f.read_text(encoding="utf-8"))
            for item in obj.get("sources",[]):
                url=item.get("url")
                if url:projects[url]=obj.get("project_id","")
        except (OSError,ValueError):pass
    rows=[]
    for item in data.get("observations",[]):
        if not item.get("source_url") or not item.get("exact_quote"):
            continue
        role=str(item.get("role") or "UNKNOWN").lower()
        needed=("Public evidence that the organization controls purchasing; "
                "official contact route; supplier/contract award status")
        if role in ("architect","agent"):
            needed="Establish owner/developer/operator and purchasing authority; agent is not buyer"
        rows.append(dict(organization=item.get("organization",""),role=role,
                         project_id=projects.get(item["source_url"],""),
                         source_url=item["source_url"],exact_quote=item["exact_quote"],
                         buyer_authority_status="NOT_VERIFIED",
                         supplier_selection_status="UNKNOWN",
                         contact_route_status="NOT_VERIFIED",
                         next_evidence_required=needed))
    with (folder/"BUYER_VERIFICATION_WORKLIST.csv").open("w",newline="",encoding="utf-8-sig") as out:
        writer=csv.DictWriter(out,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    result={"candidates_for_human_or_official_source_verification":len(rows),
            "verified_buyers":0,"unawarded_supplier_packages_verified":0,
            "status":"REVIEW_REQUIRED" if rows else "NO_SOURCE_BACKED_BUYER_CANDIDATES"}
    (folder/"BUYER_VERIFICATION_WORKLIST_STATUS.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True)
    print(json.dumps(build(p.parse_args().folder),indent=2))
