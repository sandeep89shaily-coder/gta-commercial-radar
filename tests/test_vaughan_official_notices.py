"""Offline Vaughan municipal-notice extraction tests."""
import datetime as dt
from gta_vaughan_official_notices import parse,run

HTML="""<html><main>
<h1>Public Notices</h1>
<div><h3>Notice of Public Meeting - OP.26.005 &amp; Z.26.018</h3>
<p>City File No.: OP.26.005 &amp; Z.26.018</p>
<p>Subject Land: 8000 Bathurst Street</p>
<p>Meeting Date: 11/24/2026</p>
<p>Meeting Type: Committee of the Whole (Public Meeting)</p>
<p>Notice Description: Mixed use project with commercial uses at grade.</p></div>
<div><p>City File No.: B029/25</p>
<p>Subject Land: 131 Royal Group Crescent</p>
<p>Meeting Date: 10/08/2026</p>
<p>Meeting Type: Committee of Adjustment</p>
<p>Notice Description: Industrial building expansion application DA.22.054.</p></div>
</main></html>"""

def test_vaughan_city_file_labels_only():
    parsed=parse(HTML)
    assert {x["application_id"] for x in parsed}=={"OP.26.005","Z.26.018","B029/25"}
    assert all(x["date_basis"]=="MEETING_DATE_NOT_ORIGINAL_PUBLICATION_DATE" for x in parsed)
    assert all(x["source_url"].startswith("https://www.vaughan.ca/") for x in parsed)

def test_baseline_and_repeat(tmp_path):
    folder=tmp_path/"official_exports";folder.mkdir()
    (folder/"VAUGHAN_OFFICIAL_PUBLIC_NOTICES.html").write_text(HTML,encoding="utf-8")
    first=run(tmp_path,today=dt.date(2026,11,4))
    second=run(tmp_path,today=dt.date(2026,11,5))
    assert first["application_id_rows"]==3
    assert first["new_or_changed"]==0
    assert second["new_or_changed"]==0
    assert second["automated_source_recovered"] is False

def test_reject_arbitrary_context_no_city_file(tmp_path):
    folder=tmp_path/"official_exports";folder.mkdir()
    (folder/"VAUGHAN_OFFICIAL_PUBLIC_NOTICES.html").write_text(
        "<main><p>Industrial application DA.22.054 was discussed</p></main>",
        encoding="utf-8")
    report=run(tmp_path)
    assert report["status"]=="REJECTED"
