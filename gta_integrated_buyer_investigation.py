"""Run quote-gated buyer research on official evidence from completed investigations."""
import argparse,json
from pathlib import Path
from municipal_deepseek_buyer_research import propose
def collect(folder):
    rows=[]
    for file in sorted(Path(folder).glob("AI_PROJECT_????????????????.json")):
        try:review=json.loads(file.read_text(encoding="utf-8"))
        except (ValueError,OSError):continue
        for evidence in review.get("sources",[]):
            if evidence.get("page_identity")!="EXACT_CURRENT_PERMIT_ID_IN_PAGE":continue
            snippet=str(evidence.get("text") or "")[:400].strip()
            url=evidence.get("url")
            if url and snippet:
                rows.append({"source_url":url,"quote":snippet,"project_id":review.get("project_id")})
    return rows
def run(folder,results,paid=False):
    folder=Path(folder)
    items=collect(folder)
    record={"status":"NO_EXACT_SOURCE_EXCERPTS","eligible_excerpts":len(items),
            "verified_buyers":0,"verified_unawarded_contracts":0}
    if items:
        record=propose(items[:8],results,folder/"BUYER_RELATIONSHIPS_REVIEW.json",paid=paid)
        record["eligible_excerpts"]=len(items)
    (folder/"BUYER_RESEARCH_STATUS.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    return record
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True);p.add_argument("--results",required=True);p.add_argument("--paid",action="store_true")
    a=p.parse_args();print(json.dumps(run(a.folder,a.results,a.paid),indent=2))
