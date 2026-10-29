"""Generate standalone HTML/CSV commercial intelligence report from actual AI reviews."""
from pathlib import Path
import csv,html,json

def build(folder):
    folder=Path(folder)
    records=[]
    for f in sorted(folder.glob("AI_PROJECT_????????????????.json")):
        try:
            r=json.loads(f.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            continue
        m=r.get("model_suggestions") or {}
        sources=r.get("sources") or []
        exact=[e for e in sources if e.get("page_identity")=="EXACT_CURRENT_PERMIT_ID_IN_PAGE"]
        record={"project_id":r.get("project_id",""),"address":r.get("address",""),
                "stage":m.get("project_stage",""),"developer_suggestion":m.get("developer",""),
                "operator_suggestion":m.get("operator",""),"buyer_fit":m.get("buyer_fit",""),
                "next_verification":m.get("next_verification",""),"source_count":len(sources),
                "exact_identity_sources":len(exact),"buyer_authority_verified":False,
                "supplier_selection_verified":False,"sale_ready":False,
                "source_links":[e.get("url","") for e in sources]}
        records.append(record)
    fields=["project_id","address","stage","developer_suggestion","operator_suggestion",
            "buyer_fit","next_verification","source_count","exact_identity_sources",
            "buyer_authority_verified","supplier_selection_verified","sale_ready"]
    with (folder/"COMMERCIAL_REVIEW.csv").open("w",encoding="utf-8-sig",newline="") as out:
        w=csv.DictWriter(out,fieldnames=fields);w.writeheader()
        w.writerows([{k:v.get(k) for k in fields} for v in records])
    (folder/"COMMERCIAL_REVIEW.json").write_text(json.dumps({"projects":records,
                "verified_private_opportunities":0},indent=2),encoding="utf-8")
    esc=lambda x:html.escape(str(x or ""),quote=True)
    cards=[]
    for v in records:
        links=" ".join('<a target="_blank" rel="noopener" href="'+esc(u)+'">Source</a>'
                       for u in v["source_links"] if u.startswith("https://"))
        cards.append("<article><h2>"+esc(v["address"])+"</h2><small>"+esc(v["project_id"])+
          "</small><p><b>Stage:</b> "+esc(v["stage"])+"</p><p><b>Developer (unverified):</b> "+
          esc(v["developer_suggestion"])+"</p><p><b>Commercial fit:</b> "+esc(v["buyer_fit"])+
          "</p><p><b>Next verification:</b> "+esc(v["next_verification"])+
          "</p><p><b>Exact-ID source count:</b> "+str(v["exact_identity_sources"])+
          " · Buying authority: not verified · Supplier availability: unknown</p>"+links+"</article>")
    page="""<!doctype html><html lang="en"><meta charset="utf-8"><title>GTA Radar | Commercial AI Review</title>
<style>body{font:15px system-ui;background:#0b1221;color:#edf3ff;max-width:1050px;margin:30px auto;padding:0 20px}
article{background:#19263a;border:1px solid #334863;border-radius:12px;padding:22px;margin:18px 0}
h1{font-size:28px}small{color:#b2c2d7}p{line-height:1.55}a{color:#a6d0ff}</style>
<h1>GTA Radar — Commercial investigation</h1><p>Research-only results. No private buyer, supplier
award status or unawarded contract is verified by these automated findings.</p>"""+ "".join(cards)+"</html>"
    target=folder/"COMMERCIAL_REVIEW.html"
    target.write_text(page,encoding="utf-8")
    return target
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True)
    print(build(p.parse_args().folder))
