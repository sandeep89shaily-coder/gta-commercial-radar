"""Standalone HTML/CSV/JSON commercial review.

Two kinds of project appear here:
  * AI-investigated projects (AI_PROJECT_*.json): research hints only.
  * Human-reviewed projects (REVIEWED_EVIDENCE.json): the ONLY route to
    'buyer verified', 'supplier verified' or 'sale ready'. Those flags are
    computed by reviewed_evidence.evaluate_review; nothing here sets them by hand.
"""
from pathlib import Path
import csv,datetime as dt,html,json
import reviewed_evidence

FIELDS=["project_id","address","review_status","stage","developer_suggestion","operator_suggestion",
        "buyer_organization","buyer_fit","next_verification","supplier_status","source_count",
        "exact_identity_sources","buyer_authority_verified","supplier_selection_verified",
        "contact_route_verified","sale_ready","reviewed_by","reviewed_at","source_first_publication",
        "radar_first_seen_at","radar_vs_publication_days","missing_proof"]

def _gate_fields(result):
    """Verification flags and review facts, straight from the evaluator."""
    if not result:
        return {"review_status":"AI_RESEARCH_ONLY","buyer_authority_verified":False,
                "supplier_selection_verified":False,"contact_route_verified":False,"sale_ready":False,
                "supplier_status":"UNKNOWN","buyer_organization":"","reviewed_by":"","reviewed_at":"",
                "source_first_publication":"","radar_first_seen_at":"","radar_vs_publication_days":"",
                "missing_proof":"human-reviewed official evidence (REVIEWED_EVIDENCE.json)","contact_url":""}
    published=reviewed_evidence._date(result.get("source_first_publication"))
    seen=reviewed_evidence._date(result.get("radar_first_seen_at"))
    # Positive = Radar noticed it AFTER the source published it. Never invented when either side is missing.
    lag=(seen-published).days if published and seen else ""
    return {"review_status":result["status"],"buyer_authority_verified":result["buyer_authority_verified"],
            "supplier_selection_verified":result["supplier_selection_verified"],
            "contact_route_verified":result["contact_route_verified"],"sale_ready":result["sale_ready"],
            "supplier_status":result["supplier_status"],"buyer_organization":result["buyer_organization"],
            "reviewed_by":result["reviewed_by"],"reviewed_at":result["reviewed_at"],
            "source_first_publication":result["source_first_publication"],
            "radar_first_seen_at":result.get("radar_first_seen_at",""),"radar_vs_publication_days":lag,
            "missing_proof":"; ".join(result["missing"]) if result["missing"] else "",
            "contact_url":result.get("contact_url","")}

def build(folder,as_of=None):
    folder=Path(folder)
    gate=reviewed_evidence.evaluate_folder(folder,as_of=as_of)
    results=gate["results"]
    records=[];seen=set()
    for f in sorted(folder.glob("AI_PROJECT_????????????????.json")):
        try:
            r=json.loads(f.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            continue
        pid=r.get("project_id","")
        m=r.get("model_suggestions") or {}
        sources=r.get("sources") or []
        exact=[e for e in sources if e.get("page_identity")=="EXACT_CURRENT_PERMIT_ID_IN_PAGE"]
        record={"project_id":pid,"address":r.get("address",""),
                "stage":m.get("project_stage",""),"developer_suggestion":m.get("developer",""),
                "operator_suggestion":m.get("operator",""),"buyer_fit":m.get("buyer_fit",""),
                "next_verification":m.get("next_verification",""),"source_count":len(sources),
                "exact_identity_sources":len(exact),
                "source_links":[e.get("url","") for e in sources]}
        # AI claims (verified_buying_authority, sale_ready, ...) in the dossier are deliberately ignored.
        record.update(_gate_fields(results.get(pid)))
        records.append(record);seen.add(pid)
    for pid,result in results.items():
        if pid in seen:continue
        record={"project_id":pid,"address":result.get("address") or result.get("project_name",""),
                "stage":"","developer_suggestion":"","operator_suggestion":"","buyer_fit":", ".join(result.get("service_categories",[])),
                "next_verification":"" if result["sale_ready"] else "Complete missing proof: "+"; ".join(result["missing"]),
                "source_count":0,"exact_identity_sources":0 if "project_identity" in result["missing"] else 1,
                "source_links":[]}
        record.update(_gate_fields(result))
        records.append(record)
    with (folder/"COMMERCIAL_REVIEW.csv").open("w",encoding="utf-8-sig",newline="") as out:
        w=csv.DictWriter(out,fieldnames=FIELDS);w.writeheader()
        w.writerows([{k:v.get(k) for k in FIELDS} for v in records])
    verified=sum(1 for v in records if v["sale_ready"] is True)
    (folder/"COMMERCIAL_REVIEW.json").write_text(json.dumps({
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "projects":records,"verified_private_opportunities":verified,
        "review_file":gate["review_file"],"review_file_problems":gate["problems"]},indent=2),encoding="utf-8")
    esc=lambda x:html.escape(str(x or ""),quote=True)
    cards=[]
    for v in records:
        links=" ".join('<a target="_blank" rel="noopener" href="'+esc(u)+'">Source</a>'
                       for u in v["source_links"] if str(u).startswith("https://"))
        if v["sale_ready"]:
            contact=(' · <a target="_blank" rel="noopener" href="'+esc(v.get("contact_url"))+'">Public business contact route</a>'
                     if str(v.get("contact_url","")).startswith("https://") else "")
            badge=("<p><b style='color:#7dffb0'>VERIFIED OPPORTUNITY</b> · Buyer: "+esc(v["buyer_organization"])+
                   " · Supplier status: "+esc(v["supplier_status"])+" · Reviewed by "+esc(v["reviewed_by"])+
                   " on "+esc(v["reviewed_at"])+contact+"</p>")
        else:
            badge=("<p>Buying authority: "+("verified" if v["buyer_authority_verified"] else "not verified")+
                   " · Supplier availability: "+("verified" if v["supplier_selection_verified"] else "unknown")+
                   (" · Missing: "+esc(v["missing_proof"]) if v["missing_proof"] else "")+"</p>")
        cards.append("<article><h2>"+esc(v["address"] or v["project_id"])+"</h2><small>"+esc(v["project_id"])+
          "</small><p><b>Stage:</b> "+esc(v["stage"])+"</p><p><b>Developer (unverified AI hint):</b> "+
          esc(v["developer_suggestion"])+"</p><p><b>Commercial fit:</b> "+esc(v["buyer_fit"])+
          "</p><p><b>Next verification:</b> "+esc(v["next_verification"])+
          "</p><p><b>Exact-ID source count:</b> "+str(v["exact_identity_sources"])+"</p>"+badge+links+"</article>")
    page="""<!doctype html><html lang="en"><meta charset="utf-8"><title>GTA Radar | Commercial Review</title>
<style>body{font:15px system-ui;background:#0b1221;color:#edf3ff;max-width:1050px;margin:30px auto;padding:0 20px}
article{background:#19263a;border:1px solid #334863;border-radius:12px;padding:22px;margin:18px 0}
h1{font-size:28px}small{color:#b2c2d7}p{line-height:1.55}a{color:#a6d0ff}</style>
<h1>GTA Radar — Commercial investigation</h1><p>"""+str(verified)+""" verified opportunity(ies). AI findings are research hints only;
only human-reviewed, official, dated evidence can mark a buyer, supplier status or lead as verified.</p>"""+ "".join(cards)+"</html>"
    target=folder/"COMMERCIAL_REVIEW.html"
    target.write_text(page,encoding="utf-8")
    return target
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True)
    print(build(p.parse_args().folder))
