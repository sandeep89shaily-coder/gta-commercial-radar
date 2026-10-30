"""Compare two actual GTA Radar DeepSeek runs without inventing outcomes."""
from __future__ import annotations
import argparse, json
from pathlib import Path
def load(folder):
    data={}
    for file in Path(folder).glob("AI_PROJECT_????????????????.json"):
        try: r=json.loads(file.read_text(encoding="utf-8"))
        except (ValueError,OSError):continue
        if r.get("project_id"):data[r["project_id"]]=r
    return data
def metrics(record):
    evidence=record.get("sources") or []
    accepted=[e for e in evidence if e.get("page_identity") in
              ("EXACT_CURRENT_PERMIT_ID_IN_PAGE","PROJECT_CONTEXT_NOT_APPLICATION_VERIFIED")]
    specific=sum(e.get("page_identity")=="EXACT_CURRENT_PERMIT_ID_IN_PAGE" for e in accepted)
    finding=record.get("model_suggestions") or {}
    return {"pages":len(evidence),"specific_source_pages":specific,
            "project_context_pages":len(accepted)-specific,
            "named_developer":bool(finding.get("developer")),
            "named_operator":bool(finding.get("operator")),
            "source_only":not bool(evidence),"sale_ready":bool(record.get("sale_ready"))}
def compare(before,after):
    old=load(before);new=load(after)
    rows=[{"project_id":k,"before":metrics(old[k]),"after":metrics(new[k])}
          for k in sorted(old.keys() & new.keys())]
    return {"shared_projects":len(rows),"original_projects":len(old),
            "new_projects":len(new),"comparisons":rows,
            "warning":"Comparative metrics do not confirm project facts or purchasing availability"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--before",required=True);p.add_argument("--after",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=compare(a.before,a.after)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"shared_projects":result["shared_projects"]},indent=2))
if __name__=="__main__":main()
