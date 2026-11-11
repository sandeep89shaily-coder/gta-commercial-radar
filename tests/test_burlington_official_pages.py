"""Offline acceptance tests for Burlington official-page assisted recovery."""
import csv
import datetime as dt
import json
from pathlib import Path
from gta_burlington_official_pages import _parse,run

URL="https://www.burlington.ca/en/news/current-development-projects/alinea-bronte-creek-meadows-phase-1.aspx"
HTML="""<html><main><h1>Alinea - Bronte Creek Meadows Phase 1</h1>
<h2>Proposed Development</h2><p>Employment blocks and new roads</p>
<h2>File Numbers</h2><ul><li>Official Plan Amendment: 505-02/26</li>
<li>Zoning By-law Amendment: 520-02/26</li>
<li>Draft Plan of Subdivision: 510-01/26</li></ul>
<h2>Public Meetings</h2><p>June 9, 2026</p></main></html>"""

def test_parse_official_burlington_files_without_invented_date():
    records=_parse(HTML,URL)
    assert [r["application_id"] for r in records]==["505-02/26","510-01/26","520-02/26"]
    assert all(r["date_basis"]=="NO_VERIFIED_FIRST_PUBLICATION_DATE" for r in records)
    assert all(r["provenance"]=="USER_SAVED_OFFICIAL_WEBPAGE_UNVERIFIED_CAPTURE" for r in records)

def test_reject_missing_file_section():
    import pytest
    with pytest.raises(ValueError,match="NO_FILE_NUMBERS_SECTION"):
        _parse("<main><h1>Road project</h1><p>Call 905-555-0100</p></main>",URL)

def test_assisted_baseline_repeat_and_no_live_credit(tmp_path):
    folder=tmp_path/"official_exports"/"burlington_pages"
    folder.mkdir(parents=True)
    (folder/"alinea.html").write_text(HTML,encoding="utf-8")
    with (folder/"burlington_pages_manifest.csv").open("w",encoding="utf-8",newline="") as fp:
        w=csv.DictWriter(fp,fieldnames=["url","html_file"]);w.writeheader()
        w.writerow({"url":URL,"html_file":"alinea.html"})
    first=run(tmp_path,today=dt.date(2026,11,4))
    second=run(tmp_path,today=dt.date(2026,11,5))
    assert first["application_id_rows"]==3
    assert first["new_or_changed"]==0
    assert second["new_or_changed"]==0
    assert second["automated_source_recovered"] is False
    assert second["source_authenticity_verified"] is False

def test_path_traversal_rejected(tmp_path):
    folder=tmp_path/"official_exports"/"burlington_pages"
    folder.mkdir(parents=True)
    (folder/"burlington_pages_manifest.csv").write_text("url,html_file\n"+URL+",../outside.html\n",encoding="utf-8")
    result=run(tmp_path)
    assert result["status"]=="NO_VALID_SAVED_APPLICATION_IDS"
    assert result["errors"][0]["error"].endswith("UNSAFE_HTML_FILENAME")


def test_new_current_city_post_800_burloak_plain_paragraph_label():
    url="https://www.burlington.ca/news-and-notices/posts/current-development-projects/800-burloak-dr/"
    page="""<main><h1>800 Burloak Dr.</h1><h2>Proposed Development</h2>
    <p>Mixed use eight-storey residential with ground-floor commercial units.</p>
    <div><p>File Numbers</p><ul>
    <li>Official Plan Amendment: 505-13/26</li>
    <li>Zoning By-law Amendment: 520-16/26</li>
    </ul></div>
    <div><p>Supporting Documents</p><a href="decision.pdf">
    Study dated 2020-03-02, case 535-999/24 (unrelated)</a></div>
    </main>"""
    rows=_parse(page,url)
    assert [r["application_id"] for r in rows]==["505-13/26","520-16/26"]
    assert all(r["source_url"]==url for r in rows)


def test_new_current_city_quarry_label_without_heading_markup():
    url="https://www.burlington.ca/news-and-notices/posts/current-development-projects/burlington-nelson-quarry-extension/"
    page="""<main><h1>Burlington Nelson Quarry Extension</h1>
    <h2>Proposed Development</h2><p>Expand quarry operations</p>
    <div><span>File Numbers</span><span>505-04/20</span>
    <strong>Application Processes and Timeline</strong><p>
    Appendix 535-999/23 is NOT a planning file in this section.</p></div>
    </main>"""
    rows=_parse(page,url)
    assert [r["application_id"] for r in rows]==["505-04/20"]


def test_burlington_no_file_number_not_synthesized_from_elsewhere():
    url="https://www.burlington.ca/news-and-notices/posts/current-development-projects/testing/"
    page="""<main><h1>Development proposal</h1>
    <h2>Proposed Development</h2><p>Industrial expansion</p>
    <div><p>File Numbers</p><p>To be assigned</p></div>
    <h2>Public Meetings</h2><p>Reference 520-123/26 in old notice</p></main>"""
    import pytest
    with pytest.raises(ValueError,match="NO_RECOGNIZED_BURLINGTON_FILE_NUMBERS"):
        _parse(page,url)


def test_burlington_unlabelled_number_not_treated_as_application():
    url="https://www.burlington.ca/news-and-notices/posts/current-development-projects/testing/"
    page="""<main><h1>Development proposal</h1>
    <h2>Proposed Development</h2><p>Application 505-13/26</p>
    <h2>Public Meetings</h2><p>May 10</p></main>"""
    import pytest
    with pytest.raises(ValueError,match="NO_FILE_NUMBERS_SECTION"):
        _parse(page,url)


