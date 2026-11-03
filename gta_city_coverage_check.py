"""Free source-only sixteen-city coverage diagnostic, no V6 or DeepSeek.

Usage: python gta_city_coverage_check.py --workspace "C:\...\Desktop\new data"
The collector does not overwrite the permits database or the regular V6 log.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

from gta_early_applications import run as html_run
from gta_official_gis_applications import run as tb_gis_run
from gta_additional_city_gis import run as other_gis_run
from gta_markham_circulations import run as markham_run
from gta_city_coverage_report import build
from gta_municipal_project_feed import run as municipal_run
from gta_toronto_open_data import run as toronto_csv_run
from gta_collection_truth import build as build_collection_acceptance
from gta_guelph_gis import run as guelph_gis_run

def execute(workspace):
    root=Path(workspace).expanduser()/"GTA_RADAR_RESULTS"
    root.mkdir(parents=True,exist_ok=True)
    html=html_run(root)
    tb=tb_gis_run(root)
    other=other_gis_run(root)
    municipal=municipal_run(root)
    toronto_csv=toronto_csv_run(root)
    guelph_gis=guelph_gis_run(root)
    pdf_union=(root/"DAILY_INTEGRATED_REVIEW"/"TORONTO_DOCUMENTS"/
               "COMBINED_PDF_FETCH_AUDIT.csv")
    if pdf_union.is_file():
        markham=markham_run(pdf_union,root)
    else:
        markham={"rows_extracted":0,"warning":"No previous verified official PDF union; Markham PDF capture not run by this diagnostic"}
    coverage=build(root,html,tb,other,markham,municipal,toronto_csv,guelph_gis)
    acceptance=build_collection_acceptance(root)
    print("\nGTA RADAR: MEASURED 16-CITY PLANNING APPLICATION COVERAGE (NO DEEPSEEK)")
    print("City".ljust(16)+"HTML".rjust(7)+"GIS".rjust(7)+
          "PDF".rjust(7)+"  Result")
    print("-"*95)
    for city in coverage["city_status"]:
        print(city["city"].ljust(16)+
              str(city["html_application_rows"]).rjust(7)+
              str(city["gis_application_rows"]).rjust(7)+
              str(city["pdf_application_rows"]).rjust(7)+
              "  "+city["measured_source_state"])
    print("\nCities with at least one application candidate:",
          coverage["cities_with_extracted_application_candidates"],
          "/ 16 (NOT citywide complete coverage)")
    print("Cities with no application candidates:",
          coverage["cities_without_extracted_applications"],"/ 16")
    print("Canonical unique application files:",acceptance["unique_application_files"])
    print("Canonical project-only signals:",acceptance["unique_project_only_signals"])
    print("Inactive/closed excluded from current opportunities:",acceptance["excluded_inactive_or_closed"])
    print("New or changed files for manual review:",acceptance["new_or_changed_commercial_manual_review"])
    print("Acceptance audit:",root/"GTA_RADAR_COLLECTION_ACCEPTANCE.json")
    print("Unified master CSV:",root/"GTA_RADAR_COLLECTION_MASTER.csv")
    print("Unified manual review CSV:",root/"GTA_RADAR_COLLECTION_NEW_OR_CHANGED_REVIEW.csv")
    print("16-city health CSV:",root/"GTA_RADAR_COLLECTION_HEALTH.csv")
    print("Additional municipal application ID rows:",municipal["application_id_rows"])
    print("Official project-only signals:",municipal["project_only_signals"])
    print("Municipal feed status:",root/"GTA_RADAR_MUNICIPAL_PROJECT_FEED_STATUS.json")
    print("Toronto official CSV:",toronto_csv["status"],toronto_csv["commercial_candidates"])
    print("Toronto CSV diagnostics:",root/"GTA_RADAR_TORONTO_OPEN_DATA_STATUS.json")
    print("Guelph official GIS:",guelph_gis["source_status"][0]["status"],
          guelph_gis["commercial_candidates"])
    print("Guelph GIS diagnostics:",root/"GTA_RADAR_GUELPH_GIS_STATUS.json")
    print("City audit:",root/"GTA_RADAR_CITY_COVERAGE_AUDIT.csv")
    print("Detailed status:",root/"GTA_RADAR_CITY_COVERAGE_STATUS.json")
    print("Toronto/Brampton GIS status:",root/"GTA_RADAR_STRUCTURED_APPLICATION_SOURCE_STATUS.json")
    print("Hamilton/Kitchener GIS status:",root/"GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json")
    print("No paid AI calls were made by this coverage diagnostic.")
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--workspace",required=True)
    args=p.parse_args()
    raise SystemExit(execute(args.workspace))
