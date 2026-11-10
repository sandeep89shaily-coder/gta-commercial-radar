"""Offline contract tests for Burlington's official 2026 news migration."""
from __future__ import annotations
import datetime as dt
from pathlib import Path

from gta_early_applications import SOURCES
from gta_five_city_application_recovery import (
    _valid_burlington, run, _burlington_links, VAUGHAN, STATUS
)
from gta_burlington_official_pages import _valid_url as valid_saved_page, _parse
import json

INDEX=SOURCES["Burlington"]
DETAIL=("https://www.burlington.ca/news-and-notices/posts/"
        "current-development-projects/1376-1382-plains-rd-e-bousfields-inc/")
LEGACY=("https://www.burlington.ca/en/news/current-development-projects/"
        "1376-1382-plains-rd-e.aspx")
INDEX_HTML="""<main><h1>Current Development Projects</h1>
<a href="/news-and-notices/posts/current-development-projects/1376-1382-plains-rd-e-bousfields-inc/">
1376-1382 Plains Rd E - Bousfields Inc</a>
<a href="/news-and-notices/posts/council-news-and-events/unrelated-news/">
Other official news</a>
<a href="https://elsewhere.example/current-development-projects/fake/">
Fake external project</a></main>"""
PAGE="""<main><h1>1376-1382 Plains Rd E - Bousfields Inc</h1>
<section><h2>Proposed Development</h2>
<p>A mixed-use commercial building with ground floor retail at Plains Road.</p></section>
<section><h2>File Numbers</h2><p>505-10-26 and 520-11-26</p></section>
</main>"""


def test_canonical_feed_and_strict_project_links(tmp_path):
    assert INDEX=="https://www.burlington.ca/news-and-notices/news-views/current-development-projects/"
    assert _valid_burlington(DETAIL) and valid_saved_page(DETAIL)
    assert _valid_burlington(LEGACY) and valid_saved_page(LEGACY)
    for bogus in (
        INDEX,
        "https://www.burlington.ca/news-and-notices/posts/other-news/fake/",
        "https://www.burlington.ca/news-and-notices/posts/current-development-projects/",
        DETAIL+"?redirect=https://evil.example",
        "https://www.burlington.ca.evil.example/news-and-notices/posts/current-development-projects/fake/",
        "http://www.burlington.ca/news-and-notices/posts/current-development-projects/fake/",
        "https://www.burlington.ca/news-and-notices/posts/current-development-projects/%2e%2e/",
    ):
        assert not _valid_burlington(bogus)
        assert not valid_saved_page(bogus)
    urls,errors=_burlington_links(tmp_path,lambda url: INDEX_HTML)
    assert urls==[DETAIL] and errors==[]


def test_new_city_project_page_with_exact_file_ids_is_initial_baseline(tmp_path):
    assert {r["application_id"] for r in _parse(PAGE,DETAIL)}=={
        "505-10-26","520-11-26"
    }
    def fetch(url):
        if url==INDEX:return INDEX_HTML
        if url==DETAIL:return PAGE
        if url==VAUGHAN:raise PermissionError("403")
        raise ValueError("unexpected URL:"+url)
    first=run(tmp_path,today=dt.date(2026,11,10),fetcher=fetch)
    assert first["automatic_file_id_rows_this_stage"]==2
    b=next(x for x in first["source_status"] if x["city"]=="Burlington")
    assert b["status"]=="OFFICIAL_PAGE_COLLECTION"
    assert b["links_parsed"]==1
    assert b["application_id_rows_this_stage"]==2
    assert first["new_or_changed"]==0
    second=run(tmp_path,today=dt.date(2026,11,11),fetcher=fetch)
    assert second["new_or_changed"]==0
    assert next(x for x in second["source_status"] if x["city"]=="Vaughan")[
        "automated_source_recovered_this_stage"] is False


def test_legacy_gis_fallback_keeps_policy_errors_visible(tmp_path):
    g=tmp_path/"GTA_RADAR_BURLINGTON_GIS_PROJECTS.csv"
    g.write_text("source_url\n"+LEGACY+"\n",encoding="utf-8")
    def fetch(url):
        if url==INDEX:raise ValueError("HTTP_503_OR_REDIRECT")
        if url==LEGACY:return PAGE
        if url==VAUGHAN:raise PermissionError("403")
        raise ValueError("unexpected")
    result=run(tmp_path,today=dt.date(2026,11,10),fetcher=fetch)
    b=next(x for x in result["source_status"] if x["city"]=="Burlington")
    assert b["status"]=="PARTIAL_OFFICIAL_PAGE_COLLECTION"
    assert b["links_parsed"]==1
    assert b["failed_links"] and "INDEX:" in b["failed_links"][0]
    assert b["automated_source_recovered_this_stage"] is True
