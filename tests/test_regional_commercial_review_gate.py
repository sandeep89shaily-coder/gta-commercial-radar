"""Prevent historical, awarded and already-underway projects becoming fresh leads."""
import csv,datetime as dt,json
from gta_regional_commercial_review import run,OUTPUT,NEW,EXCLUDED,STATUS
from gta_collection_truth import _aggregate,_normalize

def _write(root,name,rows):
 with (root/name).open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def capital(name,year,obs):
 return {"project_name_contract":name,"work_type":"Construction",
   "scope_of_work":"Build new electrical distribution infrastructure and pumping station.",
   "project_owner_division":"Toronto Water","source_document_url":"https://www.toronto.ca/2026-capital.pdf",
   "estimated_range":"$5M-$50M","target_sourcing_year":str(year),"target_award_year":"2028",
   "observation":obs,"first_seen_local":"2026-11-05"}

def detail(title,url,text,obs):
 return {"authority":"Waterloo","project_title":title,"project_url":url,
  "project_id":"REGIONAL_DETAIL:"+title.replace(" ","_"),
  "evidence_excerpt":text,"stage_evidence":"ASSESSMENT",
  "observation":obs,"first_seen_local":"2026-11-05",
  "source_verification":"OFFICIAL_HOST_DETAIL_HTML_EXTRACTED"}

def test_review_prioritizes_future_work_and_avoids_old_awards(tmp_path):
 _write(tmp_path,"GTA_RADAR_TORONTO_CAPITAL_PIPELINE.csv",[
  capital("Toronto Water New Equipment Station",2027,"INITIAL_BASELINE"),
  capital("Dufferin Equipment Building Historical",2024,"RECORD_CHANGED"),
 ])
 _write(tmp_path,"GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv",[
  detail("Widening project","https://www.regionofwaterloo.ca/projects/widening",
       "The Region is proposing road widening and preliminary design.", "RECORD_CHANGED"),
  detail("Completed bridge","https://www.regionofwaterloo.ca/projects/bridge",
       "Construction completed for the replacement bridge in 2024.", "RECORD_CHANGED"),
  detail("Active bridge","https://www.regionofwaterloo.ca/projects/active",
       "Construction is underway on a new pedestrian bridge.", "RECORD_CHANGED"),
 ])
 r=run(tmp_path,today=dt.date(2026,11,6))
 assert r["total_evidence_candidates"]==5
 assert r["review_records"]==2
 assert r["new_or_changed_review"]==1
 assert r["excluded_or_deferred"]==3
 assert r["verified_open_tenders"]==0
 with (tmp_path/NEW).open(encoding="utf-8-sig") as f:
  new=list(csv.DictReader(f))
 assert len(new)==1
 assert new[0]["project_name"]=="Widening project"
 assert new[0]["verified_open_tender"]=="false"
 with (tmp_path/EXCLUDED).open(encoding="utf-8-sig") as f:
  ignored={r["project_name"]:r["rejection_reason"] for r in csv.DictReader(f)}
 assert ignored["Completed bridge"]=="EXPLICIT_AWARDED_OR_COMPLETED"
 assert ignored["Active bridge"]=="CONSTRUCTION_ALREADY_STARTED_OR_UNCLEAR"
 assert ignored["Dufferin Equipment Building Historical"]=="PLANNED_SOURCING_YEAR_BEFORE_CURRENT_YEAR_OR_MISSING"

def test_pdf_parent_linked_not_counted_twice(tmp_path):
 p=detail("Reservoir project","https://www.regionofwaterloo.ca/projects/reservoir",
    "Regional water reservoir expansion at preliminary design.", "FIRST_OBSERVED")
 _write(tmp_path,"GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv",[p])
 _write(tmp_path,"GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE.csv",[{
   "project_id":p["project_id"],
   "document_url":"https://www.regionofwaterloo.ca/docs/reservoir.pdf",
   "evidence_excerpt":"Structural design and valve house replacement work for reservoir.",
   "budget_evidence":"Estimated capital cost is $25 million."}])
 r=run(tmp_path)
 assert r["review_records"]==1
 with (tmp_path/OUTPUT).open(encoding="utf-8-sig") as f:
  row=next(csv.DictReader(f))
 assert row["evidence_document_url"].endswith("reservoir.pdf")
 assert "Structural design" in row["document_excerpt"]
 assert row["estimated_contract_value"].startswith("Estimated")
 assert "not verified" not in row["verification_required"].lower()  # concrete verification instruction
 assert row["procurement_gate"]=="OPEN_TENDER_NOT_VERIFIED"

def test_no_inputs_and_baselines_no_leads(tmp_path):
 r=run(tmp_path)
 assert r["review_records"]==0
 assert r["status"]=="NO_EVIDENCE"
 assert r["new_or_changed_review"]==0

def test_canonical_rejects_old_approved_application_despite_change():
 old=_normalize("TORONTO_CKAN",{"city":"Toronto",
     "application_id":"13 144733 STE 20 OZ","project_id":"a",
     "address":"305 King St","description":"Retail and office 50-storey mixed-use building.",
     "current_status":"OMB Approved","first_seen_local":"2026-11-02",
     "observation":"RECORD_CHANGED"})
 assert old
 result=_aggregate([old])
 assert result[0]["review_priority"]=="BASELINE_OR_UNVERIFIED"
 assert result[0]["quality_flag"]=="INACTIVE_OR_CLOSED"


def test_municipal_location_requires_unambiguous_official_evidence():
 from gta_regional_commercial_review import _municipality
 assert _municipality("Markham Reservoir Rehabilitation","Upgrade water reservoir.")=="Markham"
 assert _municipality("Sewage Works Project",
   "Project covers the City of Markham and City of Pickering.")==""
 assert _municipality("Regional Wastewater Programme",
   "The new treatment system is located in the City of Cambridge.")=="Cambridge"
 assert _municipality("York Region infrastructure programme",
   "General infrastructure overview for the Region.")==""


def test_waterloo_river_road_completed_season_does_not_discard_phase_two(tmp_path):
    # Region project 0787: a finished season and older road segment coexist
    # with Phase 2 (2027-2032) and its Highway 7/8 bridge/ramp work.
    row=detail("River Road/Bleams Road",
      "https://www.regionofwaterloo.ca/programs-and-services/roads-and-transportation/road-construction/construction-projects/river-roadbleams-road/",
      "Construction is finished for the 2025 season. The new Bleams Road extension is open. "
      "Phase 1 includes bridge across Schneider Creek (2020-2027). "
      "Phase 2 includes extension of River Road and bridge over Highway 7/8. "
      "Construction phase 2: 2027-2032.", "RECORD_CHANGED")
    _write(tmp_path,"GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv",[row])
    summary=run(tmp_path,today=dt.date(2026,11,6))
    assert summary["review_records"]==1
    with (tmp_path/OUTPUT).open(encoding="utf-8-sig") as f:
        candidate=next(csv.DictReader(f))
    assert candidate["priority"]=="PROJECT_STAGE_REVIEW"
    assert candidate["rejection_reason"]=="FUTURE_PHASE_PACKAGE_STATUS_UNVERIFIED"
    assert candidate["city"]==""
    assert candidate["verified_open_tender"]=="false"
    assert summary["new_or_changed_review"]==1


def test_waterloo_westmount_prior_work_complete_but_phase_two_on_hold(tmp_path):
    row=detail("Westmount Road | Victoria to Erb",
      "https://www.regionofwaterloo.ca/programs-and-services/roads-and-transportation/road-construction/construction-projects/westmount-road-victoria-to-erb/",
      "The first phase of the Westmount Road project was completed earlier this year "
      "from Highland Road to Victoria Street. The second phase from Victoria Street "
      "to Erb Street is currently on hold. Road resurfacing is planned for 2028 "
      "and the remaining improvements follow the Class EA.", "RECORD_CHANGED")
    _write(tmp_path,"GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv",[row])
    summary=run(tmp_path,today=dt.date(2026,11,6))
    assert summary["review_records"]==0
    assert summary["excluded_or_deferred"]==1
    with (tmp_path/EXCLUDED).open(encoding="utf-8-sig") as f:
        candidate=next(csv.DictReader(f))
    assert candidate["priority"]=="RECHECK_ON_HOLD"
    assert candidate["rejection_reason"]=="REMAINING_PROJECT_WORK_ON_HOLD_NOT_COMPLETED"
    assert candidate["verified_open_tender"]=="false"


def test_later_phase_already_awarded_still_excluded(tmp_path):
    row=detail("Industrial watermain improvements",
      "https://www.regionofwaterloo.ca/projects/industrial-watermain",
      "Phase 1 of construction completed in 2024. Phase 2 was awarded "
      "in 2026 with installation and upgrade scheduled for 2027.", "RECORD_CHANGED")
    _write(tmp_path,"GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv",[row])
    run(tmp_path,today=dt.date(2026,11,6))
    with (tmp_path/EXCLUDED).open(encoding="utf-8-sig") as f:
        candidate=next(csv.DictReader(f))
    assert candidate["priority"]=="EXCLUDE"
    assert candidate["rejection_reason"]=="EXPLICIT_AWARDED_OR_COMPLETED"
