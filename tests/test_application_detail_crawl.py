"""Offline regressions for bounded official application detail collection."""
from gta_early_applications import _detail_urls, _enrich_from_details

URL="https://www.milton.ca/business-development/planning/development-notices/"

def test_detail_links_only_same_host_application_pages():
    markup='''<a href="/business-development/planning/notice-of-complete-application/">Notice of Complete Application</a>
    <a href="https://evil.example/notice-of-complete-application/">external</a>
    <a href="/business-development/planning/report.pdf">Development application PDF</a>
    <a href="/news">Latest news</a>'''
    assert _detail_urls(markup,"Milton",URL)==[
        "https://www.milton.ca/business-development/planning/notice-of-complete-application/"]

def test_detail_page_extracts_actual_application_number():
    markup='<a href="/business-development/planning/development-application/">Development application</a>'
    detail='<article><h3>SP-2026-0123 Industrial warehouse expansion</h3></article>'
    def fetcher(url):
        assert url.endswith("/development-application/")
        return detail
    rows,audit=_enrich_from_details(markup,"Milton",URL,fetcher)
    assert len(rows)==1
    assert rows[0]["application_id"]=="SP-2026-0123"
    assert audit["detail_pages_fetched"]==1

def test_detail_page_failure_not_counted_as_success():
    markup='<a href="/business-development/planning/development-application/">Development application</a>'
    def denied(url):
        raise ValueError("ROBOTS_ACCESS_DENIED")
    rows,audit=_enrich_from_details(markup,"Milton",URL,denied)
    assert rows==[]
    assert audit["detail_pages_fetched"]==0
    assert audit["detail_page_failures"]
