"""Daily GTA Radar release acceptance from real on-disk outputs."""
from pathlib import Path
import json,datetime as dt
from gta_commercial_review_html import build
from gta_ai_quality_comparison import compare

def acceptance(folder,baseline=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    build(folder)
    p=json.loads((folder/"COMMERCIAL_REVIEW.json").read_text(encoding="utf-8"))
    rows=p["projects"]
    evidence=sum(x["exact_identity_sources"]>0 for x in rows)
    buyer=sum(x["buyer_authority_verified"] is True for x in rows)
    supplier=sum(x["supplier_selection_verified"] is True for x in rows)
    report={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "investigated_projects":len(rows),"official_exact_id_projects":evidence,
            "verified_buying_authorities":buyer,"verified_unawarded_packages":supplier,
            "sale_ready":sum(x["sale_ready"] for x in rows),
            "production_acceptance":False,
            "failures":[],
            "claims":"Official evidence does not by itself prove an unawarded work package"}
    if not rows:report["failures"].append("NO_LIVE_AI_PROJECT_REVIEWS")
    if evidence==0:report["failures"].append("NO_EXACT_ID_SOURCE_EVIDENCE")
    if buyer==0:report["failures"].append("NO_VERIFIED_PRIVATE_BUYERS")
    if supplier==0:report["failures"].append("NO_VERIFIED_UNAWARDED_WORK_PACKAGES")
    if baseline and Path(baseline).is_dir():
        report["quality_comparison"]=compare(baseline,folder)
    else:report["quality_comparison_status"]="NO_PRIOR_RUN_SUPPLIED"
    (folder/"RELEASE_ACCEPTANCE.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True);p.add_argument("--baseline")
    a=p.parse_args();print(json.dumps(acceptance(a.folder,a.baseline),indent=2))
