"""Offline fixture tests for source-aware municipal project collection."""
from gta_municipal_project_feed import _parse

def test_halton_official_file_number():
    page="""<table><tr><td>263</td><td>279 Guelph Street</td>
    <td>D11SPA26.003</td><td>Proposed dairy plant and office expansion</td></tr></table>"""
    rows=_parse("Halton Hills",page,
      "https://www.haltonhills.ca/developmentproposalsunderreview")
    assert len(rows)==1
    assert rows[0]["application_id"]=="D11SPA26.003"

def test_oakville_ward_application():
    page="""<ul><li>Pinty's Delicious Foods Inc. - 2714 Bristol Circle -
    1403.071/01</li></ul>"""
    rows=_parse("Oakville",page,
      "https://www.oakville.ca/business-development/planning-development/active-development-applications/ward-6-development-and-site-plan-applications/")
    assert len(rows)==1
    assert rows[0]["application_id"]=="1403.071/01"

def test_milton_notice_is_not_invented_application():
    page="""<a href="/business-development/planning/notice-of-complete-application-0-quarry/">
     Notice of Complete Application: 0 Quarry Crescent</a>"""
    rows=_parse("Milton",page,
      "https://www.milton.ca/business-development/planning-and-development/development-applications/development-application-notices/")
    assert len(rows)==1
    assert rows[0]["record_kind"]=="PROJECT_INDEX_SIGNAL"
    assert rows[0]["application_id"]==""

def test_guelph_project_index_is_unverified():
    page="""<table><tr><td>501 Hanlon Creek Boulevard</td>
    <td>Active Development Files, Official Plan, Zone changes</td></tr></table>"""
    rows=_parse("Guelph",page,
      "https://guelph.ca/city-government/planning-and-development/current-development-applications/")
    assert len(rows)==1 and rows[0]["application_id"]==""


def test_hamilton_complete_application_detail():
    page="""<h1>Complete Application for 925 Main Street West</h1>
    <p>Proposal: A 29-storey mixed use building with commercial space.</p>
    <p>Address: 925 Main Street West (Ward 1)</p>
    <p>File Number: DPA-2026-00207</p>"""
    rows=_parse("Hamilton",page,
      "https://www.hamilton.ca/city-council/news-notices/news-releases/complete-application-925-main-street-west-hamilton")
    assert len(rows)==1 and rows[0]["application_id"]=="DPA-2026-00207"

def test_brampton_featured_application():
    page="""<section><h3>Featured Application: June 15, 2026</h3>
    <p>Office mixed-use block (City File: OZS-2025-0048) Ward 10</p></section>"""
    rows=_parse("Brampton",page,"https://letsconnect.brampton.ca/yourcityplans")
    assert rows and any(r["application_id"]=="OZS-2025-0048" for r in rows)


def test_one_ward_failure_does_not_suppress_other_ward_baseline(tmp_path):
    from gta_municipal_project_feed import run, STATE
    import json
    city="Oakville"
    ward1="https://www.oakville.ca/business-development/planning-development/active-development-applications/ward-1-development-and-site-plan-applications/"
    ward2="https://www.oakville.ca/business-development/planning-development/active-development-applications/ward-2-development-and-site-plan-applications/"
    def fetch(url):
        if url==ward1:raise ValueError("ROBOTS_ACCESS_DENIED")
        return "<li>AVID-IGH Hotel - 170 North Service Road West - 1517.001/01</li>"
    first=run(tmp_path,sources={city:[ward1,ward2]},fetcher=fetch)
    assert first["application_id_rows"]==1
    assert first["source_status"][0]["pages_fetched"]==1
    assert not first["new_or_changed"]
    state=json.loads((tmp_path/STATE).read_text())
    assert ward2 in state["sources"][city]["pages"]
    assert ward1 not in state["sources"][city]["pages"]
    second=run(tmp_path,sources={city:[ward1,ward2]},fetcher=fetch)
    assert second["new_or_changed"]==0


def test_halton_js_table_absent_preserves_major_project_signals():
    page="""<a href="/work/planning-development/active-development-applications/37-king-street">37 King Street, Georgetown (Exchange Hotel)</a>"""
    rows=_parse("Halton Hills",page,
      "https://www.haltonhills.ca/developmentproposalsunderreview")
    assert len(rows)==1 and rows[0]["record_kind"]=="PROJECT_INDEX_SIGNAL"
    assert rows[0]["application_id"]==""


def test_vaughan_public_notice_excludes_minor_variance_and_extracts_commercial():
    page="""<main><p>City File No.: OP.26.005 & Z.26.018</p>
    <p>Subject Land: 8000 Bathurst Street</p>
    <p>Meeting Date: 11/24/2026</p>
    <p>Notice Description: Proposed mixed-use residential buildings with commercial
    retail space at grade.</p><p>Notice Type: Proposal for an Official Plan Amendment</p>
    <p>City File No.: A110/26</p><p>Subject Land: 227 Creek Boulevard</p>
    <p>Meeting Date: 10/29/2026</p>
    <p>Notice Description: Relief requested for a cabana.</p></main>"""
    rows=_parse("Vaughan",page,
        "https://www.vaughan.ca/about-city-vaughan/departments/office-city-clerk/public-notices")
    assert {r["application_id"] for r in rows}=={"OP.26.005","Z.26.018"}

def test_kitchener_projects_never_claim_application_number():
    page="""<a href="/strategic-plans-and-projects/projects/downtown-fire-station-and-residential-development/">
    Downtown fire station and residential development</a>"""
    rows=_parse("Kitchener",page,
        "https://www.kitchener.ca/strategic-plans-and-projects/projects/")
    assert len(rows)==1 and rows[0]["application_id"]==""
    assert rows[0]["record_kind"]=="PROJECT_INDEX_SIGNAL"


def test_guelph_page_has_real_application_id_not_address_guess():
    from gta_municipal_project_feed import _detail_project
    page="""<h1>501 Hanlon Creek Boulevard</h1><h2>File Number OZS26-011</h2>
    <p>Applications received to permit a veterinary service in an
    existing employment-area property and associated plan amendment.</p>"""
    result=_detail_project("Guelph",page,"https://guelph.ca/2026/10/501-hanlon-creek-boulevard/")
    assert len(result)==1
    assert result[0]["application_id"]=="OZS26-011"

def test_guelph_address_only_does_not_invent_file():
    from gta_municipal_project_feed import _detail_project
    result=_detail_project("Guelph","<h1>70 Monarch Road</h1><p>Industrial facility amendment</p>",
                           "https://guelph.ca/2026/09/70-monarch-road/")
    assert result==[]

def test_halton_official_file_no_html():
    from gta_municipal_project_feed import _detail_project
    page="""<h1>279 Guelph Street</h1><p>Proposed dairy plant expansion and
    office development (D11SPA26.003).</p>"""
    result=_detail_project("Halton Hills",page,
         "https://www.haltonhills.ca/work/planning-development/active-development-applications/279-guelph-street")
    assert len(result)==1
    assert result[0]["application_id"]=="D11SPA26.003"
