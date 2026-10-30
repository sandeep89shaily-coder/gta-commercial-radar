"""Unified, evidence-first intelligence materialization for GTA Radar.

Reads completed project dossiers and existing source registers. Never invents
buyer authority, supplier awards or publication timestamps. Does not charge AI.
"""
from __future__ import annotations
import argparse,datetime as dt,json,hashlib
from pathlib import Path
from urllib.parse import urlparse

def _read(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError,OSError):return {}

def _id(kind,value):
    return kind+":"+hashlib.sha256(str(value).strip().casefold().encode()).hexdigest()[:16]

def build(results,review):
    results=Path(results);review=Path(review)
    review.mkdir(parents=True,exist_ok=True)
    nodes={};edges={};projects=[]
    def node(kind,key,**fields):
        nid=_id(kind,key)
        if nid not in nodes:nodes[nid]={"id":nid,"kind":kind,"key":key,**fields}
        return nid
    def edge(src,dst,relationship,evidence_url,verification):
        key=(src,dst,relationship,evidence_url)
        edges[key]={"source":src,"target":dst,"relationship":relationship,
                    "evidence_url":evidence_url,"verification":verification}
    for file in sorted(review.glob("AI_PROJECT_????????????????.json")):
        r=_read(file)
        if not r.get("project_id"):continue
        pid=str(r["project_id"])
        project=node("project",pid,address=r.get("address",""),
                     status="AI_REVIEW_ONLY")
        src=r.get("source_url","")
        if isinstance(src,str) and src.startswith("https://"):
            sid=node("source",src)
            edge(project,sid,"OFFICIAL_RECORD_LINK",src,"SOURCE_REFERENCE_ONLY")
        exact=0
        for item in r.get("sources",[]):
            uri=item.get("url","")
            if not isinstance(uri,str) or not uri.startswith("https://"):continue
            verified=item.get("page_identity")=="EXACT_CURRENT_PERMIT_ID_IN_PAGE"
            sid=node("source",uri,source_type=item.get("kind",""))
            edge(project,sid,"EVIDENCED_BY",uri,
                 "EXACT_APPLICATION_ID" if verified else "CONTEXT_ONLY")
            exact+=int(verified)
        model=r.get("model_suggestions") or {}
        source_text=" ".join(str(item.get("text","")) for item in r.get("sources",[])
                            if item.get("page_identity")=="EXACT_CURRENT_PERMIT_ID_IN_PAGE").casefold()
        roles=[]
        for role in ("developer","operator","owner","tenant","contractor"):
            company=str(model.get(role) or "").strip()
            if not company:continue
            org=node("organization",company)
            evidenced=bool(exact and company.casefold() in source_text)
            edge(project,org,"SUGGESTED_"+role.upper(),
                 src,"NAME_IN_EXACT_RECORD_ROLE_UNCONFIRMED" if evidenced else "AI_HYPOTHESIS")
            roles.append({"role":role,"organization":company,
                          "name_visible_in_exact_record":evidenced,
                          "purchasing_authority_verified":False})
        projects.append({"project_id":pid,"address":r.get("address",""),
                         "exact_application_evidence_count":exact,
                         "candidate_roles":roles,
                         "buyer_authority_verified":False,
                         "supplier_unawarded_verified":False,
                         "commercial_status":"RESEARCH_ONLY",
                         "missing":["verified purchasing authority","supplier selection evidence"]})
    try:
        from municipal_document_registry import report
        doc=report(Path(__file__).parent/"config"/"municipal_document_sources.csv",review)
    except Exception as exc:
        doc={"status":"REGISTRY_ERROR","error_type":type(exc).__name__}
    feeds=_read(results/"EARLY_SIGNAL_FEED_AUDIT.json")
    timing=_read(results/"EARLY_DISCOVERY_PROOF.json")
    buyer=_read(review/"BUYER_RESEARCH_STATUS.json")
    summary={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
             "project_dossiers":len(projects),"exact_id_project_dossiers":sum(p["exact_application_evidence_count"]>0 for p in projects),
             "verified_private_leads":0,"verified_buying_authorities":0,
             "graph_nodes":len(nodes),"graph_relationships":len(edges),
             "document_registry_sources":doc.get("registered_sources",0),
             "document_retrieval_confirmed":doc.get("documents_retrieved",0),
             "early_feed_indexes_checked":len(feeds.get("feeds",[])),
             "early_feed_candidate_links":len(feeds.get("candidate_links",[])),
             "lead_time_measurable_projects":timing.get("measurable",0),
             "buyer_research_status":buyer.get("status","NOT_RUN"),
             "production_ready":False}
    obj={"summary":summary,"projects":projects,"nodes":list(nodes.values()),
         "edges":list(edges.values())}
    (review/"GTA_RADAR_INTELLIGENCE_GRAPH.json").write_text(
        json.dumps(obj,indent=2,ensure_ascii=False),encoding="utf-8")
    (review/"GTA_RADAR_INTELLIGENCE_STATUS.json").write_text(
        json.dumps(summary,indent=2),encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True);p.add_argument("--review",required=True)
    args=p.parse_args();print(json.dumps(build(args.results,args.review),indent=2))
if __name__=="__main__":main()
