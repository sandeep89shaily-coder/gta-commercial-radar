"""Unified, evidence-first intelligence materialization for GTA Radar.

Reads completed project dossiers and existing source registers. Never invents
buyer authority, supplier awards or publication timestamps. Does not charge AI.
"""
from __future__ import annotations
import argparse,datetime as dt,json,hashlib,csv
from pathlib import Path
from urllib.parse import urlparse
import reviewed_evidence

def _read(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError,OSError):return {}

def _id(kind,value):
    return kind+":"+hashlib.sha256(str(value).strip().casefold().encode()).hexdigest()[:16]

def build(results,review):
    results=Path(results);review=Path(review)
    review.mkdir(parents=True,exist_ok=True)
    gate=reviewed_evidence.evaluate_folder(review)["results"]
    if not gate and results.is_dir():gate=reviewed_evidence.evaluate_folder(results)["results"]
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
                         "buyer_authority_verified":bool(gate.get(pid,{}).get("buyer_authority_verified")),
                         "supplier_unawarded_verified":bool(gate.get(pid,{}).get("supplier_selection_verified")),
                         "commercial_status":gate.get(pid,{}).get("status","RESEARCH_ONLY"),
                         "missing":gate.get(pid,{}).get("missing",["verified purchasing authority","supplier selection evidence"])})
    try:
        from municipal_document_registry import report
        doc=report(Path(__file__).parent/"config"/"municipal_document_sources.csv",review)
    except Exception as exc:
        doc={"status":"REGISTRY_ERROR","error_type":type(exc).__name__}
    feeds=_read(results/"EARLY_SIGNAL_FEED_AUDIT.json")
    timing=_read(results/"EARLY_DISCOVERY_PROOF.json")
    buyer=_read(review/"BUYER_RESEARCH_STATUS.json")
    meeting_audits={folder.name:_read(folder/"INTEGRATED_PILOT_AUDIT.json")
                    for folder in (review/"MEETINGS").glob("*") if folder.is_dir()}
    pdf_audit=_read(review/"TORONTO_DOCUMENTS"/"TORONTO_MEETING_PDF_SUMMARY.json")
    multi=_read(review/"OTHER_CITY_DOCUMENTS"/"MULTICITY_DOCUMENT_STATUS.json")
    pdf_union=review/"TORONTO_DOCUMENTS"/"COMBINED_PDF_FETCH_AUDIT.csv"
    captured=0
    if pdf_union.is_file():
        with pdf_union.open(encoding="utf-8-sig",newline="") as stream:
            captured=sum(r.get("status")=="CAPTURED" for r in csv.DictReader(stream))
    candidate_file=results/"GTA_RADAR_DOCUMENT_PROJECT_CANDIDATES.csv"
    candidates=[]
    if candidate_file.is_file():
        with candidate_file.open(encoding="utf-8-sig",newline="") as stream:
            candidates=list(csv.DictReader(stream))
    for candidate in candidates:
        cid=candidate.get("document_candidate_id")
        source=candidate.get("pdf_url","")
        if not cid or not isinstance(source,str) or not source.startswith("https://"):
            continue
        c=node("document_candidate",cid,
               city=candidate.get("city",""),verification="UNVERIFIED_REVIEW_ONLY")
        document=node("source",source,source_type="CAPTURED_MUNICIPAL_PDF")
        edge(c,document,"ORIGINAL_DOCUMENT_SOURCE",source,"PDF_CAPTURE_REVIEW_ONLY")
    doc_ai=_read(review/"DOCUMENT_AI"/"TORONTO_AI_DOCUMENT_BATCH_SUMMARY.json")

    summary={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
             "project_dossiers":len(projects),"exact_id_project_dossiers":sum(p["exact_application_evidence_count"]>0 for p in projects),
             "verified_private_leads":sum(g["sale_ready"] for g in gate.values()),
             "verified_buying_authorities":sum(g["buyer_authority_verified"] for g in gate.values()),
             "graph_nodes":len(nodes),"graph_relationships":len(edges),
             "document_registry_sources":doc.get("registered_sources",0),
             "document_retrieval_confirmed":captured,
             "document_registry_retrieval_confirmed":doc.get("documents_retrieved",0),
             "other_city_pdfs_captured":multi.get("direct_pdf_captured",0),
             "document_candidate_records_review_only":len(candidates),
             "early_feed_indexes_checked":len(feeds.get("feeds",[])),
             "early_feed_candidate_links":len(feeds.get("candidate_links",[])),
             "lead_time_measurable_projects":timing.get("measurable",0),
             "buyer_research_status":buyer.get("status","NOT_RUN"),
             "meeting_discovery_cities_attempted":len(meeting_audits),
             "meeting_discovery_cities_index_fetched":sum(
                 v.get("official_index_status")=="INDEX_FETCHED_LINK_ONLY"
                 for v in meeting_audits.values()),
             "toronto_meeting_agendas_fetched":pdf_audit.get("meetings_fetched",0),
             "toronto_meeting_pdfs_downloaded":pdf_audit.get("pdf_downloaded",0),
             "document_ai_reviews":doc_ai.get("review_outputs",0),
             "document_ai_errors":doc_ai.get("errors",0),
             "production_ready":bool(any(g["sale_ready"] for g in gate.values())
                                     and _read(review/"RELEASE_ACCEPTANCE.json").get("production_acceptance") is True)}
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
