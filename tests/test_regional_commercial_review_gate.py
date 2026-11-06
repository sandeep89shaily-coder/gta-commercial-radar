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
 _write(tmp_path,"GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE.csv":[{
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
