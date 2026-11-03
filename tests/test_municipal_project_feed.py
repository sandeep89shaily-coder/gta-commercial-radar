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
