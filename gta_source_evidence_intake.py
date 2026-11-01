"""Free bounded source-text recovery and claim verification intake.

Only direct record excerpts are proposed, never AI summaries. Missing official
identity, publication dates, purchasing authority and supplier status remain unknown.
"""
from __future__ import annotations
import argparse,csv,json,datetime as dt
from pathlib import Path
import auto_verify
import gta_select_first_investigations as first
import candidate_scoring as scoring

SOURCE_FILES=("GTA_RADAR_V8_PENDING_QUEUE.csv","GTA_RADAR_V8_PROJECTS.csv",
              "GTA_RADAR_V4_PROJECTS_FOR_AI.csv","GTA_RADAR_PROJECT_OPPORTUNITIES.csv")
def load_csv(path):
    try:
        with Path(path).open(encoding="utf-8-sig",newline="") as stream:return list(csv.DictReader(stream))
    except (OSError,UnicodeError,ValueError):return []
def recover(results,top=10):
    results=Path(results)
    candidates=first.load_records(results/first.DEFAULT_FILE)
    by_id={}
    for filename in SOURCE_FILES:
        for item in load_csv(results/filename):
            pid=(item.get("project_id") or "").strip()
            desc=(item.get("official_description") or item.get("description") or "").strip()
            if pid and desc and item.get("record_source_url","").startswith("https://"):
                if pid not in by_id or len(desc)>len(by_id[pid].get("description","")):
                    by_id[pid]={**item,"description":desc}
    recovered=[];needs=[]
    for item in candidates:
        pid=item.get("project_id","")
        if first.has_source_text(item):
            recovered.append(item)
        elif pid in by_id:
            recovered.append({**item,"description":by_id[pid]["description"],
                               "record_source_url":by_id[pid]["record_source_url"],
                               "source_recovery_basis":"EXISTING_SOURCED_QUEUE_NOT_LIVE_REFETCH"})
        else:
            needs.append({"project_id":pid,"address":item.get("address",""),
                          "source_url":item.get("record_source_url",""),
                          "reason":"NO_MATCHING_SOURCED_RECORD_IN_LOCAL_FILES"})
    selection=first.prioritize(recovered,top)
    return selection,needs

def propose(row):
    """Use exact source description, without inventing missing milestones."""
    url=(row.get("record_source_url") or "").strip()
    desc=(row.get("official_description") or row.get("description") or "").strip()
    pid=(row.get("project_id") or "").strip()
    if not pid or not url.startswith("https://") or len(desc)<25:return None
    # A quoted source record can support scope, but cannot establish company
    # ownership, a direct government page identity, or historical publication.
    claim={"official_url":url,"excerpt":desc[:450]}
    return {"project_id":pid,"address":row.get("address",""),
            "organization":row.get("official_company","") or "",
            "supplier_status":"UNKNOWN","claims":{"scope_evidence":claim,
                                                          "project_source":claim}}

def run(results,out,*,top=10,fetcher=None):
    results=Path(results);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    selection,missing=recover(results,top)
    chosen=selection["top"]
    specs=[spec for row in chosen if (spec:=propose(next(
        (r for r in first.load_records(results/first.DEFAULT_FILE) if r.get("project_id")==row["project_id"]),row))) ]
    # Recovered descriptions are also eligible for verification.
    for row in chosen:
        if any(s["project_id"]==row["project_id"] for s in specs):continue
        spec=propose(row)
        if spec:specs.append(spec)
    summary={"candidate_count":len(chosen),"claim_specs":len(specs),
             "source_refresh_required":missing+selection["needs_source_refresh"],
             "verified_claims":0,"human_confirmations_created":0}
    if fetcher is not None and specs:
        reviews=[];status=[]
        for spec in specs:
            review,details=auto_verify.build_review(spec,fetcher)
            reviews.append(review);status.append({"project_id":spec["project_id"],"claims":details})
            summary["verified_claims"]+=sum(x["status"]=="AUTO_VERIFIED" for x in details.values())
        auto_verify.write_auto_file(results,reviews)
        summary["claim_status"]=status
    # Never touch the owner's reviewed evidence or source databases.
    dated=out/("SOURCE_INTAKE_"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
    dated.write_text(json.dumps({"summary":summary,"specs":specs},indent=2),encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True);p.add_argument("--out",required=True)
    p.add_argument("--top",type=int,default=10);p.add_argument("--verify",action="store_true")
    a=p.parse_args()
    fetcher=(lambda url:auto_verify.fetch_page(url)) if a.verify else None
    print(json.dumps(run(a.results,a.out,top=a.top,fetcher=fetcher),indent=2))
if __name__=="__main__":main()
