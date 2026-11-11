"""Offline acceptance tests: next four cities must not fabricate commercial leads."""
import datetime as dt
import csv

from gta_next_four_municipalities import (
    SOURCES, _safe, _links, _file_numbers, ALL, CHANGES, run,
)


def _sample():
    ajax = SOURCES["Ajax"]
    detail = "https://ajax.ca/news-notices/proposed-outdoor-event-facility/"
    home = ('<main><a href="/news-notices/proposed-outdoor-event-facility/">'
            'Proposed Outdoor Event Facility - 688 Taunton Road West</a>'
            '<a href="https://evil.example/news-notices/fake">Proposed development</a>'
            '</main>')
    notice = ('<main><h1>Proposed Outdoor Event Facility - 688 Taunton Road West</h1>'
              '<p>Application Z17/26 would permit a commercial event venue.</p>'
              '<p>Property located at 688 Taunton Road West.</p>'
              '<p>Contact: 905-555-1212.</p></main>')
    return ajax, detail, home, notice


def test_sources_are_four_additional_municipalities_not_sixteen():
    assert set(SOURCES) == {"Ajax", "Whitby", "Clarington", "Brantford"}
    from gta_early_applications import SOURCES as MAIN
    assert not (set(SOURCES) & set(MAIN))


def test_original_city_id_and_initial_baseline_do_not_alert(tmp_path):
    ajax, detail, home, notice = _sample()
    def fetch(url):
        return home if url == ajax else notice
    first = run(tmp_path, today=dt.date(2026, 11, 11),
                sources={"Ajax": ajax}, fetcher=fetch)
    assert first["application_id_rows"] == 1
    assert first["verified_fresh_commercial_leads"] == 0
    assert first["new_or_changed_review_only"] == 0
    with (tmp_path / ALL).open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["application_id"] == "Z17/26"
    assert rows[0]["observation"] == "INITIAL_BASELINE_NOT_NEW_PUBLICATION"
    assert rows[0]["verified_open_procurement"] == "False"

    second = run(tmp_path, today=dt.date(2026, 11, 12),
                 sources={"Ajax": ajax}, fetcher=fetch)
    assert second["new_or_changed_review_only"] == 0
    assert second["application_id_rows"] == 1


def test_new_id_after_baseline_is_undated_held(tmp_path):
    ajax, detail, home, notice = _sample()
    def fetch(url):
        return home if url == ajax else notice
    run(tmp_path, today=dt.date(2026, 11, 11),
        sources={"Ajax": ajax}, fetcher=fetch)
    changed = notice.replace("Z17/26", "Z17/26 and application Z18/26")
    result = run(tmp_path, today=dt.date(2026, 11, 12),
                 sources={"Ajax": ajax},
                 fetcher=lambda u: home if u == ajax else changed)
    assert result["application_id_rows"] == 2
    assert result["new_or_changed_review_only"] == 1
    assert result["verified_fresh_commercial_leads"] == 0
    with (tmp_path / CHANGES).open(encoding="utf-8-sig") as f:
        new = list(csv.DictReader(f))
    assert new[0]["application_id"] == "Z18/26"
    assert new[0]["observation"] == "FIRST_OBSERVED_UNDATED_HELD"


def test_whitby_inline_is_only_project_signal(tmp_path):
    source = SOURCES["Whitby"]
    html = ('<main><ul><li>114 Winchester Road East and 7 Duke Street '
            '- Zoning By-law Amendment submitted by Winchester LP '
            'for a mixed-use commercial project</li></ul></main>')
    result = run(tmp_path, sources={"Whitby": source},
                 fetcher=lambda _: html)
    assert result["project_only_signals"] == 1
    assert result["application_id_rows"] == 0
    assert result["verified_fresh_commercial_leads"] == 0


def test_brantford_map_index_without_file_id_not_coverage(tmp_path):
    source = SOURCES["Brantford"]
    page = '<main><h1>Planning applications</h1><a href="/map">View Map</a></main>'
    result = run(tmp_path, sources={"Brantford": source},
                 fetcher=lambda _: page)
    assert result["source_status"][0]["status"] == "INDEX_ONLY_NO_PROJECT_APPLICATION_RECORDS"
    assert result["cities_with_application_ids"] == 0
    assert result["verified_citywide_coverage"] == 0


def test_clarington_notice_number_extracted_only_when_labeled(tmp_path):
    source = SOURCES["Clarington"]
    target = "https://www.clarington.net/news/posts/public-meeting-notice-three-developments/"
    home = '<main><a href="/news/posts/public-meeting-notice-three-developments/">Public meeting notice</a></main>'
    page = ('<main><h1>Public meeting notice - Industrial proposal</h1>'
            '<p>Application Number: ZBA2026-004.</p>'
            '<p>Warehouse proposed at 1631 Baseline Road.</p></main>')
    result = run(tmp_path, sources={"Clarington": source},
                 fetcher=lambda x: home if x == source else page)
    assert result["application_id_rows"] == 1
    assert result["source_status"][0]["fetched_notice_pages"] == 1


def test_bad_official_link_rejected_and_no_unlabeled_ids():
    source, _, home, _ = _sample()
    assert len(_links("Ajax", home, source)) == 1
    assert not _safe("https://evil.example/proposed-development", source)
    assert not _safe(source + "?token=secret", source)
    assert _file_numbers("Call 905-555-1212 or review by-law Z17/26") == []
    assert _file_numbers("File Number: Z17/26") == ["Z17/26"]


def test_failed_notice_does_not_mutate_baseline_or_manufacture_changes(tmp_path):
    ajax, detail, home, notice = _sample()
    run(tmp_path, sources={"Ajax": ajax},
        fetcher=lambda x: home if x == ajax else notice)
    previous = (tmp_path / ALL).read_bytes()
    def denied(url):
        if url == ajax:
            return home
        raise PermissionError("ROBOTS_DENIED")
    result = run(tmp_path, sources={"Ajax": ajax}, fetcher=denied)
    assert result["new_or_changed_review_only"] == 0
    assert result["source_status"][0]["status"] == "FAILED"
    assert result["source_status"][0]["retained_prior_rows"] == 1
    assert (tmp_path / ALL).read_bytes() == previous


def test_changed_detail_is_review_not_new_publication(tmp_path):
    ajax, _, home, notice = _sample()
    run(tmp_path, sources={"Ajax": ajax},
        fetcher=lambda x: home if x == ajax else notice)
    revised = notice.replace("commercial event venue", "industrial event venue")
    result = run(tmp_path, sources={"Ajax": ajax},
                 fetcher=lambda x: home if x == ajax else revised)
    assert result["new_or_changed_review_only"] == 1
    assert result["verified_fresh_commercial_leads"] == 0
    with (tmp_path / CHANGES).open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    assert row["observation"] == "RECORD_CHANGED_REVIEW"
