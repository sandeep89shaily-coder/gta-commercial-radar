"""Evidence and regression tests for two independent Radar opportunity lanes."""
from __future__ import annotations
import csv
import datetime as dt
import json
from pathlib import Path

from gta_opportunity_lanes import (
    run,PRIVATE_TOP,PRIVATE_ALL,PRIVATE_CHANGES,PRIVATE_FRESH,PRIVATE_REJECTED,
    GOV_TOP,GOV_CHANGES,STATUS,DASHBOARD
)

def write(root,name,rows):
    with (root/name).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def read(root,name):
    with (root/name).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def notice(case="520-15/26",title="4495 North Service Rd. - Dream Summit Industrial",
           url="https://www.burlington.ca/en/news/current-development-projects/4495-North-Service-Road.aspx",
           work="Proposed two one-storey industrial buildings with accessory office uses.",
           status="UNDER REVIEW",observation="INITIAL_BASELINE"):
    return dict(project_id="OFFICIAL_PAGE:BURLINGTON:"+case,city="Burlington",
      application_id=case,project_title=title,description=work,current_status=status,
      record_source_url=url,source_record_date="",
      date_basis="NO_VERIFIED_FIRST_PUBLICATION_DATE",
      first_seen_local="2026-11-06",observation=observation,
      provenance="LIVE_OFFICIAL_PROJECT_PAGE_EXPLICIT_FILE_NUMBER")

def gov(name,score_year="2027",obs="INITIAL_BASELINE"):
    return dict(record_id="GOVERNMENT:"+name,authority="Toronto",city="Toronto",
      project_name=name,scope_of_work="Regional water main and road bridge construction",
      buyer_organization="City of Toronto",source_type="TORONTO_CAPITAL_PDF",
      project_url="https://www.toronto.ca/wp-content/uploads/2026/05/capital.pdf",
      source_date="",source_date_basis="TARGET_YEAR_IS_NOT_FIRST_PUBLICATION",
      priority="MONITOR_PLANNED",stage_hint="PLANNED_CAPITAL_PROCUREMENT",
      estimated_contract_value="Over $50M",target_sourcing_year=score_year,
      first_seen_local="2026-11-06",observation=obs)

def test_private_projects_not_displaced_by_public_capital(tmp_path):
    first=notice()
    second=notice("505-13/26","800 Burloak Dr.",
        "https://www.burlington.ca/en/news/current-development-projects/800-burloak-dr.aspx",
        "8-storey mixed-use building with 275 units and 967 square metres of retail at grade.")
    third=notice("520-16/26","800 Burloak Dr.",second["record_source_url"],
        second["description"])
    write(tmp_path,"GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv",[first,second,third])
    write(tmp_path,"GTA_RADAR_REGIONAL_COMMERCIAL_REVIEW.csv",
          [gov("Black Creek Sewer"),gov("Dufferin Office Building")])
    result=run(tmp_path,today=dt.date(2026,11,6))
    assert result["private_top"]==2
    assert result["government_top"]==2
    assert result["private_verified_recent_publications"]==0
    private=read(tmp_path,PRIVATE_TOP)
    assert len(private)==2
    assert all(x["lane"]=="PRIVATE_DEVELOPMENT" for x in private)
    assert not any("Black Creek" in x["project_name"] for x in private)
    dream=next(x for x in private if x["project_name"].startswith("4495"))
    assert dream["company_name"]=="Dream Summit Industrial"
    assert dream["private_ownership_evidence"]=="PRIVATE_SECTOR_LIKELY_OWNER_NOT_VERIFIED"
    assert dream["contact_status"]=="NO_PROJECT_ASSIGNED_CONTACT_VERIFIED"
    assert dream["email"]=="" and dream["phone"]==""
    burloak=next(x for x in private if x["project_name"].startswith("800"))
    assert set(burloak["application_ids"].split("; "))=={"505-13/26","520-16/26"}
    assert burloak["stage_gate"]=="PLANNING_OR_SITE_PLAN_REVIEW"
    assert "mixed-use" in burloak["nature_of_work"].lower()
    assert read(tmp_path,PRIVATE_CHANGES)==[]
    assert read(tmp_path,PRIVATE_FRESH)==[]
    public=read(tmp_path,GOV_TOP)
    assert len(public)==2
    assert all(x["lane"]=="GOVERNMENT_PROCUREMENT" for x in public)
    assert all(x["procurement_status"]=="CURRENT_TENDER_AND_AWARD_STATUS_NOT_VERIFIED" for x in public)
    text=(tmp_path/DASHBOARD).read_text()
    assert "Private development" in text and "Government procurement" in text
    assert "Dream Summit Industrial" in text


def test_old_city_application_lower_priority_and_dated_approval_is_not_new(tmp_path):
    write(tmp_path,"GTA_RADAR_COLLECTION_MASTER.csv",[
      dict(canonical_id="toronto:file:08",city="Toronto",record_kind="APPLICATION_ID",
          application_id="08 215022 ESC 42 SA",address="601 MILNER AVE",
          description="Industrial warehouse expansion and retail storage space",
          current_status="Under Review",application_year_hint="2008",
          evidence_urls="https://open.toronto.ca/dataset/development-applications/",
          first_seen_local="2026-11-06",observation="RECORD_CHANGED"),
      dict(canonical_id="toronto:file:22",city="Toronto",record_kind="APPLICATION_ID",
          application_id="22 100012 STE 24 OZ",address="100 EXAMPLE ST",
          description="Commercial and industrial warehouse with loading bays",
          current_status="OMB Approved",application_year_hint="2022",
          evidence_urls="https://open.toronto.ca/dataset/development-applications/",
          first_seen_local="2026-11-06",observation="FIRST_OBSERVED")])
    result=run(tmp_path,today=dt.date(2026,11,6))
    assert result["private_projects_eligible"]==1
    row=read(tmp_path,PRIVATE_TOP)[0]
    assert row["reason"]=="OLD_APPLICATION_YEAR_REVIEW"
    assert row["freshness_class"]=="CHANGED_IN_RADAR_PUBLISHER_DATE_NOT_VERIFIED"
    assert result["private_verified_recent_publications"]==0


def test_private_source_not_assigned_government_owner(tmp_path):
    write(tmp_path,"GTA_RADAR_COLLECTION_MASTER.csv",[
      dict(city="Toronto",record_kind="APPLICATION_ID",
          application_id="26 125111 ESC 21 SA",address="12 CIVIC ST",
          description="City of Toronto capital programme, new public municipal office.",
          current_status="Under Review",
          evidence_urls="https://open.toronto.ca/dataset/development-applications/",
          first_seen_local="2026-11-06",observation="FIRST_OBSERVED"),
      dict(city="Toronto",record_kind="APPLICATION_ID",
          application_id="26 125112 ESC 21 SA",address="15 INDUSTRIAL RD",
          description="New industrial warehouse and 3 loading docks.",
          current_status="Under Review",
          evidence_urls="https://open.toronto.ca/dataset/development-applications/",
          first_seen_local="2026-11-06",observation="FIRST_OBSERVED")])
    result=run(tmp_path,today=dt.date(2026,11,6))
    assert result["private_projects_eligible"]==1
    assert read(tmp_path,PRIVATE_TOP)[0]["address"]=="15 INDUSTRIAL RD"
    assert result["private_source_rows_discarded"]["PUBLIC_OWNER_OR_SCOPE"]==1
    assert result["private_changes_to_verify"]==1
    assert result["private_verified_recent_publications"]==0


def test_first_radar_observation_not_official_recent_publication(tmp_path):
    write(tmp_path,"GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv",[
        notice(observation="FIRST_OBSERVED")])
    state=run(tmp_path,today=dt.date(2026,11,6))
    assert state["private_changes_to_verify"]==1
    assert state["private_verified_recent_publications"]==0
    row=read(tmp_path,PRIVATE_CHANGES)[0]
    assert row["freshness_class"]=="FIRST_OBSERVED_IN_RADAR_NOT_NEW_PUBLICATION"


def test_explicit_publication_date_must_be_verified_and_recent(tmp_path):
    x=notice(observation="FIRST_OBSERVED")
    x["source_record_date"]="2026-11-04"
    x["date_basis"]="VERIFIED_FIRST_PUBLICATION_DATE"
    write(tmp_path,"GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv",[x])
    state=run(tmp_path,today=dt.date(2026,11,6))
    assert state["private_verified_recent_publications"]==1
    assert len(read(tmp_path,PRIVATE_FRESH))==1
    assert len(read(tmp_path,PRIVATE_CHANGES))==0


def test_appealed_and_permitted_less_priority_than_active_planning(tmp_path):
    x=notice("520-50/26","2500 Active Dr. - Alpha Industrial",
        "https://burlington.ca/en/news/current-development-projects/active.aspx")
    y=notice("520-51/26","3000 Appealed Dr. - Beta Industrial",
        "https://burlington.ca/en/news/current-development-projects/appeal.aspx",
        status="APPEALED")
    write(tmp_path,"GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv",[x,y])
    run(tmp_path,today=dt.date(2026,11,6))
    rows=read(tmp_path,PRIVATE_TOP)
    assert rows[0]["project_name"].startswith("2500")
    assert rows[1]["stage_gate"]=="APPEALED_OR_ON_HOLD"


def test_missing_sources_produce_valid_empty_headers(tmp_path):
    result=run(tmp_path,today=dt.date(2026,11,6))
    assert result["private_top"]==0 and result["government_top"]==0
    assert len(read(tmp_path,PRIVATE_TOP))==0
    assert len(read(tmp_path,GOV_TOP))==0
    assert json.loads((tmp_path/STATUS).read_text())["government_open_tenders_verified"]==0


def test_html_escapes_source_titles_and_csv_formula(tmp_path):
    x=notice(title="123 Warehouse Dr - Legit Industrial Inc <script>x</script>",
             work="Industrial warehouse with <img src=x onerror=alert(1)>")
    write(tmp_path,"GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv",[x])
    run(tmp_path)
    text=(tmp_path/DASHBOARD).read_text()
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "<img src=x" not in text


def test_november7_burlington_duplicate_blank_address_and_2004_case_excluded(tmp_path):
    # Reproduces actual Nov 7 source-layout: detailed rows have addresses,
    # generic canonical project-only signals may have blank site addresses.
    present=notice()
    burloak=notice("520-16/26","800 Burloak Dr.",
       "https://www.burlington.ca/en/news/current-development-projects/800-burloak-dr.aspx",
       "Proposed eight-storey mixed-use building, retail space and 275 units.")
    ancient=notice("520-11/04","Emshih Developments Prince William Dr.",
       "https://www.burlington.ca/en/news/current-development-projects/emshih-developments-prince-william-dr.aspx",
       "Applications dating to March 2004 for a neighbourhood commercial shopping development.",
       status="APPROVED")
    ancient["address"]="700 and 800 Burloak Drive"
    write(tmp_path,"GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv",
          [present,burloak,ancient])
    write(tmp_path,"GTA_RADAR_COLLECTION_MASTER.csv",[
        dict(city="Burlington",record_kind="PROJECT_ONLY_SIGNAL",
           address="",application_id="",description=present["description"],
           current_status="UNDER REVIEW",evidence_urls=present["record_source_url"],
           first_seen_local="2026-11-07",observation="UNCHANGED"),
        dict(city="Burlington",record_kind="PROJECT_ONLY_SIGNAL",
           address="",application_id="",description=burloak["description"],
           current_status="UNDER REVIEW",evidence_urls=burloak["record_source_url"],
           first_seen_local="2026-11-07",observation="UNCHANGED")])
    state=run(tmp_path,today=dt.date(2026,11,7))
    titles=[r["project_name"] for r in read(tmp_path,PRIVATE_TOP)]
    assert len(titles)==2
    assert len(set(titles))==2
    assert not any("Prince William" in title for title in titles)
    excluded=read(tmp_path,PRIVATE_REJECTED)
    assert any(r["stage_gate"]=="HISTORICAL_APPROVAL_EXCLUDE" for r in excluded)
    assert state["private_projects_eligible"]==2


def test_industrial_2026_prioritized_above_mixed_residential_and_old(tmp_path):
    write(tmp_path,"GTA_RADAR_COLLECTION_MASTER.csv",[
        dict(city="Toronto",record_kind="APPLICATION_ID",
             application_id="26 115080 WET 01 SA",
             address="8-28 WESTMORE DR",application_year_hint="2026",
             description="Three industrial buildings totaling 18220 m2, 40 warehouse units.",
             current_status="Under Review",
             evidence_urls="https://open.toronto.ca/dataset/development-applications/",
             first_seen_local="2026-11-07",observation="UNCHANGED"),
        dict(city="Toronto",record_kind="APPLICATION_ID",
             application_id="21 165080 STE 21 OZ",
             address="100 CUMBERLAND ST",application_year_hint="2021",
             description="A 40-storey mixed use building with 600 residential dwelling units and retail.",
             current_status="Under Review",
             evidence_urls="https://open.toronto.ca/dataset/development-applications/",
             first_seen_local="2026-11-07",observation="UNCHANGED")])
    run(tmp_path,today=dt.date(2026,11,7))
    ranked=read(tmp_path,PRIVATE_TOP)
    assert ranked[0]["address"]=="8-28 WESTMORE DR"
    assert int(ranked[0]["score"])>int(ranked[1]["score"])


def test_government_commercial_significance_breaks_alphabetical_tie(tmp_path):
    small=gov("Appraisal Reports")
    small["scope_of_work"]="To complete new appraisal reports for property assets."
    small["estimated_contract_value"]="Up to $5M"
    large=gov("Black Creek Tunnel Construction")
    large["scope_of_work"]="Construction of major sanitary tunnel relief system."
    large["estimated_contract_value"]="Over $50M"
    write(tmp_path,"GTA_RADAR_REGIONAL_COMMERCIAL_REVIEW.csv",[small,large])
    run(tmp_path,today=dt.date(2026,11,7))
    data=read(tmp_path,GOV_TOP)
    assert data[0]["project_name"]=="Black Creek Tunnel Construction"
    assert all(r["procurement_status"]=="CURRENT_TENDER_AND_AWARD_STATUS_NOT_VERIFIED" for r in data)
