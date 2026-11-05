import csv
import datetime as dt
import json

from gta_regional_project_details import _evidence, run, OUTPUT, CHANGES, STATUS


def seed(root):
    rows=[
        {"record_id":"r1","authority":"York","signal_type":"INFRASTRUCTURE_INDEX",
         "project_title":"King City water reservoir expansion",
         "source_url":"https://www.york.ca/projects/king-city-reservoir",
         "official_index_url":"https://www.york.ca/projects"},
        {"record_id":"r2","authority":"Peel","signal_type":"ENVIRONMENTAL_ASSESSMENT_INDEX",
         "project_title":"Industrial wastewater pumping station",
         "source_url":"https://peelregion.ca/construction/pump-station",
         "official_index_url":"https://peelregion.ca/construction"},
        {"record_id":"r3","authority":"Waterloo","signal_type":"INFRASTRUCTURE_INDEX",
         "project_title":"Waterloo road improvement project",
         "source_url":"https://www.regionofwaterloo.ca/roads/corridor",
         "official_index_url":"https://www.regionofwaterloo.ca/roads"},
        {"record_id":"noise","authority":"York","signal_type":"INFRASTRUCTURE_INDEX",
         "project_title":"Official project listing",
         "source_url":"https://www.york.ca/projects","official_index_url":"https://www.york.ca/projects"},
        {"record_id":"wrong","authority":"Peel","signal_type":"INFRASTRUCTURE_INDEX",
         "project_title":"Wastewater project pdf",
         "source_url":"https://peelregion.ca/files/project.pdf","official_index_url":"https://peelregion.ca/construction"},
        {"record_id":"host","authority":"York","signal_type":"INFRASTRUCTURE_INDEX",
         "project_title":"Water expansion",
         "source_url":"https://evil.example/projects","official_index_url":"https://www.york.ca/projects"},
    ]
    with (root/"GTA_RADAR_REGIONAL_EARLY_RECORDS.csv").open("w",encoding="utf-8",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def page(number="27", amount="$30 million"):
    return ('<html><main><h1>King City Reservoir Expansion</h1>'
            '<p>The proposed reservoir expansion is at preliminary design stage.</p>'
            f'<p>The estimated capital budget is {amount} for construction of the facility.</p>'
            f'<p>Detailed design of pump station number {number} is part of the project.</p>'
            '<time datetime="2026-10-30">October 30</time>'
            '<a href="/documents/assessment.pdf">Study</a>'
            '</main></html>')


def test_evidence_budget_and_date_not_invented():
    x=_evidence(page(),{"project_title":"fallback"})
    assert x["budget_evidence"].find("$30 million") >= 0
    assert x["explicit_source_date"]=="2026-10-30"
    assert x["source_date_basis"]=="OFFICIAL_PAGE_TIME_ELEMENT_NOT_FIRST_PUBLICATION"
    assert x["document_links_count"]==1


def test_three_authorities_baseline_repeat_and_changed(tmp_path):
    seed(tmp_path)
    url="https://www.york.ca/projects/king-city-reservoir"
    def fetch(_): return page()
    first=run(tmp_path,today=dt.date(2026,11,4),fetcher=fetch)
    assert first["project_detail_records"]==3 and first["new_or_changed"]==0
    assert first["verified_procurement_opportunities"]==0
    second=run(tmp_path,today=dt.date(2026,11,5),fetcher=fetch)
    assert second["new_or_changed"]==0
    third=run(tmp_path,today=dt.date(2026,11,6),fetcher=lambda u:page(amount="$35 million") if u==url else page())
    assert third["new_or_changed"]==1
    with (tmp_path/CHANGES).open(encoding="utf-8-sig") as fp:
        changes=list(csv.DictReader(fp))
    assert changes[0]["authority"]=="York"
    assert changes[0]["first_seen_local"]=="2026-11-04"


def test_one_source_failure_does_not_discard_other_details(tmp_path):
    seed(tmp_path)
    def fetch(url):
        if "peelregion" in url:raise ValueError("POLICY_DENIED:robots")
        return page()
    result=run(tmp_path,fetcher=fetch)
    assert result["project_detail_records"]==2
    assert result["failed_links"]==1
    assert result["failures"][0]["authority"]=="Peel"
    assert json.loads((tmp_path/STATUS).read_text())["paid_ai_calls"]==0


def test_without_index_no_false_success(tmp_path):
    r=run(tmp_path,fetcher=lambda _:page())
    assert r["status"]=="NO_VERIFIABLE_PROJECT_DETAILS"
    assert r["selected_project_links"]==0
