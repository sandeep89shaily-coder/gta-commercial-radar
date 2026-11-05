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
