"""City-by-city measured coverage; configuration never counts as live coverage."""
from __future__ import annotations
import csv,json
from pathlib import Path
from gta_early_applications import SOURCES

OUTPUT="GTA_RADAR_CITY_COVERAGE_AUDIT.csv"
STATUS="GTA_RADAR_CITY_COVERAGE_STATUS.json"
COLUMNS=("city","official_landing_page","index_fetch","html_application_rows",
         "gis_application_rows","pdf_application_rows","municipal_application_rows","project_only_signals","official_csv_application_rows",
         "live_official_notice_application_rows","total_source_candidate_rows_not_deduplicated",
         "measured_source_state","missing_capability","source_details")

def build(root,html_status,toronto_brampton_gis,other_gis,markham,municipal=None,toronto_csv=None,guelph_gis=None,five_city=None):
    root=Path(root)
    html={r["city"]:r for r in html_status.get("city_status",[])
          if isinstance(r,dict) and r.get("city")}
    gis={}
    for summary in (toronto_brampton_gis,other_gis,guelph_gis or {}):
        for row in summary.get("source_status",[]):
            if not isinstance(row,dict):continue
            city=row.get("city")
            if city not in SOURCES:continue
            status=row.get("status","")
            gis.setdefault(city,[]).append({
                "source":row.get("source",""),"status":status,
                "count":int(row.get("commercial_candidates",0) or 0),
            })
    municipal_map={r['city']:r for r in (municipal or {}).get('source_status',[])}
    live={r.get("city"):r for r in (five_city or {}).get("source_status",[])
          if isinstance(r,dict) and r.get("automated_source_recovered_this_stage")}
    results=[]
    for city,url in SOURCES.items():
        h=html.get(city,{})
        html_n=int(h.get("actual_application_rows",0) or 0)
        layers=gis.get(city,[])
        gis_n=sum(r["count"] for r in layers if r["status"] in
                  ("OK_BASELINE","OK_MONITORED","BASELINE_COMPLETE","COLLECTED"))
        pdf_n=int(markham.get("rows_extracted",0) or 0) if city=="Markham" else 0
        mun=municipal_map.get(city,{})
        mun_n=int(mun.get('application_id_rows',0) or 0)
        signal_n=int(mun.get('project_only_signals',0) or 0)
        csv_n=(int((toronto_csv or {}).get("commercial_candidates",0) or 0)
               if city=="Toronto" and (toronto_csv or {}).get("status") in
               ("BASELINED","COLLECTED") else 0)
        live_n=int(live.get(city,{}).get("application_id_rows_this_stage",0) or 0)
        total=html_n+gis_n+pdf_n+mun_n+csv_n+live_n
        index_status=h.get("fetch_status","NOT_RUN")
        if total>0:
            measured="APPLICATION_CANDIDATES_EXTRACTED_NOT_CITYWIDE_COMPLETE"
            missing="Actual project verification, reliable posting/change dates and full citywide coverage"
        elif index_status=="FETCH_FAILED" and not any(r["status"] in
                  ("OK_BASELINE","OK_MONITORED","BASELINE_COMPLETE","COLLECTED") for r in layers):
            measured="SOURCE_FETCH_FAILED"
            missing="Functional permitted project-data collector"
        else:
            measured="NO_APPLICATION_RECORDS_EXTRACTED"
            missing="Official application-level adapter; index response alone is insufficient"
        details=" | ".join(r["source"]+":"+r["status"] for r in layers)
        if mun:details+=" | MunicipalFeed:"+mun.get("state","UNKNOWN")
        if city=="Toronto" and toronto_csv:details+=" | TorontoCKAN:"+toronto_csv.get("status","UNKNOWN")
        if live_n:details+=" | LiveOfficialNotice:"+str(live_n)
        if city=="Markham":details+=" | Markham PDF:"+str(pdf_n)
        results.append({"city":city,"official_landing_page":url,
              "index_fetch":index_status,"html_application_rows":html_n,
              "gis_application_rows":gis_n,"pdf_application_rows":pdf_n,
              "municipal_application_rows":mun_n,"project_only_signals":signal_n,
              "official_csv_application_rows":csv_n,
              "live_official_notice_application_rows":live_n,
              "total_source_candidate_rows_not_deduplicated":total,
              "measured_source_state":measured,"missing_capability":missing,
              "source_details":details})
    with (root/OUTPUT).open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLUMNS)
        writer.writeheader();writer.writerows(results)
    summary={"cities_configured":len(SOURCES),
      "cities_with_extracted_application_candidates":sum(
          x["total_source_candidate_rows_not_deduplicated"]>0 for x in results),
      "cities_without_extracted_applications":sum(
          x["total_source_candidate_rows_not_deduplicated"]==0 for x in results),
      "candidate_source_rows_not_deduplicated":sum(
          x["total_source_candidate_rows_not_deduplicated"] for x in results),
      "verified_citywide_complete_coverage":0,
      "project_only_signals_not_counted_as_applications":sum(x["project_only_signals"] for x in results),
      "city_status":results,"csv":str(root/OUTPUT),
      "warning":"Official source configuration is not usable coverage. Count is source-candidate rows, not unique fresh commercial leads. GIS, PDF and HTML may overlap; official first-publication dates and citywide completeness remain unverified."}
    (root/STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
