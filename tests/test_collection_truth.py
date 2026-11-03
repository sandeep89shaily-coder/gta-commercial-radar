"""Offline collection acceptance tests: no old leads, no inflated coverage."""
import csv
from gta_collection_truth import _normalize,_aggregate,build

def test_inactive_legacy_application_not_salable():
    old=_normalize("TORONTO_CKAN",{"city":"Toronto","application_id":"10 123456 STE 20 OZ",
        "description":"INACTIVE Industrial warehouse redevelopment",
        "current_status":"Under Review","observation":"FIRST_OBSERVED"})
    assert _aggregate([old])[0]["review_priority"]=="BASELINE_OR_UNVERIFIED"

def test_baseline_never_promoted():
    row=_normalize("TORONTO_CKAN",{"city":"Toronto","application_id":"26 123456 STE 20 SA",
        "description":"Industrial warehouse","observation":"INITIAL_BASELINE"})
    assert _aggregate([row])[0]["review_priority"]=="BASELINE_OR_UNVERIFIED"

def test_cross_source_same_file_merges_sources():
    a=_normalize("EARLY_HTML",{"city":"Brampton","application_id":"OZS-2025-0048",
        "description":"Office and retail plaza","observation":"RECORD_CHANGED"})
    b=_normalize("MUNICIPAL_HTML",{"city":"Brampton","application_id":"OZS 2025 0048",
        "description":"Office and retail plaza","observation":"UNCHANGED"})
    out=_aggregate([a,b])
    assert len(out)==1 and out[0]["source_count"]==2
    assert out[0]["review_priority"]=="MANUAL_REVIEW"

def test_project_only_not_counted_as_application(tmp_path):
    with (tmp_path/"GTA_RADAR_MUNICIPAL_PROJECT_FEED.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=("city","project_id","project_title",
                            "record_kind","source_url","observation"))
        w.writeheader();w.writerow({"city":"Halton Hills","project_id":"x",
             "project_title":"New industrial park","record_kind":"PROJECT_INDEX_SIGNAL",
             "source_url":"https://www.haltonhills.ca/work/test",
             "observation":"FIRST_OBSERVED"})
    result=build(tmp_path)
    assert result["unique_application_files"]==0
    assert result["unique_project_only_signals"]==1
    assert result["new_or_changed_commercial_manual_review"]==0
    assert len(result["per_city"])==16

def test_changed_relevant_app_review_only():
    row=_normalize("EARLY_HTML",{"city":"Mississauga","application_id":"OZ/OPA 26-15 W5",
        "description":"New hotel and banquet hall","observation":"RECORD_CHANGED"})
    out=_aggregate([row])[0]
    assert out["review_priority"]=="MANUAL_REVIEW"
    assert out["application_year_hint"]=="2026" or out["application_year_hint"]==""
