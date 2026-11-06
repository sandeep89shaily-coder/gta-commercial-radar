import csv
import datetime as dt
import json
from gta_municipal_official_notices import run as notices,_vaughan_rows,_burlington_rows,_burlington_links,VAUGHAN,BURLINGTON,OUTPUT as NOTICES
from gta_evidence_backed_commercial_review import run as review,OUTPUT,WATCH

BURLINGTON_URL="https://www.burlington.ca/en/news/current-development-projects/3110_South_Service_Rd.aspx"
BURLINGTON_HTML="""<main><h1>3110 South Service Rd.</h1>
<p>Status - Under Review</p><p>Ward 4 Site Address 3110 South Service Road</p>
<h2>Proposed Development</h2><p>A proposed two-storey industrial data centre requiring 20MW of electrical capacity and commercial cooling systems.</p>
<h2>File Number</h2><p>535-004/26</p>
</main>"""
VAUGHAN_HTML="""<main><h1>Public Notices</h1>
<p>Notice Type: Proposal for an Official Plan Amendment
City File No.: OP.26.005 &amp; Z.26.018
Subject Land: 8000 Bathurst Street
Meeting Date: 11/24/2026
Meeting Type: Committee of the Whole (Public Meeting)
Notice Description: Two phased mixed-use development of four residential buildings and commercial ground-floor units.</p>
</main>"""

def test_exact_file_ids_only_no_index_guessing():
    items=_burlington_rows(BURLINGTON_HTML,BURLINGTON_URL)
    assert len(items)==1
    assert items[0]["application_id"]=="535-004/26"
    assert items[0]["source_publication_date"]==""
    v=_vaughan_rows(VAUGHAN_HTML)
    assert sorted(x["application_id"] for x in v)==["OP.26.005","Z.26.018"]
    assert all(x["source_publication_date"]=="" for x in v)

def test_notice_source_boundaries():
    html='<main><a href="/en/news/current-development-projects/3110_South_Service_Rd.aspx">3110 Data Centre</a><a href="https://evil.example/3110.aspx">external</a></main>'
    assert _burlington_links(html)==[BURLINGTON_URL]
    assert _vaughan_rows('<main><p>Phone 905-832-2281. Council at 8000 Bathurst St.</p></main>')==[]

def test_baseline_and_repeat_two_cities(tmp_path):
    index='<main><a href="/en/news/current-development-projects/3110_South_Service_Rd.aspx">3110 Data Centre</a></main>'
    def fetch(url):
        if url==BURLINGTON:return index
        if url==BURLINGTON_URL:return BURLINGTON_HTML
        if url==VAUGHAN:return VAUGHAN_HTML
        raise ValueError("OTHER_HOST")
    first=notices(tmp_path,today=dt.date(2026,11,6),fetcher=fetch)
    assert first["cities_with_application_ids"]==2
    assert first["application_id_rows"]==3
    assert first["new_or_changed"]==0
    second=notices(tmp_path,today=dt.date(2026,11,7),fetcher=fetch)
    assert second["new_or_changed"]==0
    with (tmp_path/NOTICES).open(encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==3

def test_city_access_denied_not_promoted(tmp_path):
    result=notices(tmp_path,fetcher=lambda url: (_ for _ in ()).throw(ValueError("POLICY_DENIED:ROBOTS_ACCESS_DENIED")))
    assert result["application_id_rows"]==0
    assert all(x["status"]=="FAILED" for x in result["source_status"])

def write(root,name,fields,records):
    with (root/name).open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(records)

def test_commercial_gate_separates_baseline_past_sourcing_closed_and_changes(tmp_path):
    capital=[
        {"project_id":"C-OLD","project_name_contract":"Old capital planned project",
         "scope_of_work":"Water treatment infrastructure expansion","target_sourcing_year":"2024",
         "observation":"RECORD_CHANGED"},
        {"project_id":"C-FUTURE","project_name_contract":"Future major capital project",
         "scope_of_work":"Construction of wastewater pumping facility","target_sourcing_year":"2027",
         "observation":"FIRST_OBSERVED"},
    ]
    write(tmp_path,"GTA_RADAR_TORONTO_CAPITAL_PIPELINE.csv",list(capital[0]),capital)
    regional=[
        {"project_id":"R1","authority":"York","project_title":"Reservoir",
         "stage_evidence":"CONSTRUCTION","evidence_excerpt":"The project was completed in 2024.","observation":"RECORD_CHANGED"},
        {"project_id":"R2","authority":"Waterloo","project_title":"Road works",
         "stage_evidence":"ASSESSMENT","evidence_excerpt":"New detailed design for highway bridges","observation":"RECORD_CHANGED"},
        {"project_id":"R3","authority":"Peel","project_title":"Pumping works",
         "stage_evidence":"ASSESSMENT","evidence_excerpt":"Environmental assessment for plant upgrade","observation":"INITIAL_BASELINE"}
    ]
    write(tmp_path,"GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv",list(regional[0]),regional)
    report=review(tmp_path,today=dt.date(2026,11,6))
    assert report["review_candidates"]==1
    assert report["watchlist_records"]==3
    assert report["excluded_source_explicit"]==1
    assert report["verified_open_tenders"]==0
    with (tmp_path/OUTPUT).open(encoding="utf-8-sig") as f: r=list(csv.DictReader(f))
    assert [x["project_id"] for x in r]==["R2"]
    with (tmp_path/WATCH).open(encoding="utf-8-sig") as f: w=list(csv.DictReader(f))
    assert {x["project_id"] for x in w}=={"C-OLD","C-FUTURE","R3"}

def test_closed_application_and_new_application_not_confused(tmp_path):
    data=[
        {"project_id":"M1","city":"Vaughan","project_title":"Warehouse development",
         "scope_of_work":"New warehouse and storage",
         "current_status":"Closed","observation":"RECORD_CHANGED"},
        {"project_id":"M2","city":"Burlington","project_title":"Industrial site plan",
         "scope_of_work":"Proposed factory expansion",
         "current_status":"Under Review","observation":"FIRST_OBSERVED"}]
    write(tmp_path,"GTA_RADAR_MUNICIPAL_OFFICIAL_APPLICATIONS.csv",list(data[0]),data)
    result=review(tmp_path,today=dt.date(2026,11,6))
    assert result["review_candidates"]==1
    assert result["excluded_source_explicit"]==1
