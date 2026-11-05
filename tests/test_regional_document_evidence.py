import csv
import datetime as dt
import json
from types import SimpleNamespace

import gta_regional_document_evidence as mod
from gta_regional_project_details import _evidence as html_evidence


def seed(root):
    rows = [
        {"project_id":"y1","authority":"York","project_title":"Reservoir expansion",
         "project_url":"https://www.york.ca/projects/reservoir",
         "official_pdf_urls_json":json.dumps([
             "https://www.york.ca/docs/reservoir.pdf",
             "https://evil.example/data.pdf",
             "https://www.york.ca/docs/other.pdf"])},
        {"project_id":"p1","authority":"Peel","project_title":"Pump replacement",
         "project_url":"https://peelregion.ca/projects/pumps",
         "official_pdf_urls_json":json.dumps(["https://peelregion.ca/reports/pumps.pdf"])},
        {"project_id":"w1","authority":"Waterloo","project_title":"Road expansion",
         "project_url":"https://www.regionofwaterloo.ca/projects/road",
         "official_pdf_urls_json":"not json"},
    ]
    with (root/mod.INPUT).open("w",newline="",encoding="utf-8") as fp:
        w=csv.DictWriter(fp,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)


def test_html_collects_only_same_host_pdf_links():
    html=('<main><h1>Reservoir project</h1>'
          '<p>The water reservoir expansion is entering detailed design.</p>'
          '<a href="/reports/study.pdf">Study</a>'
          '<a href="https://evil.example/assessment.pdf">External</a></main>')
    result=html_evidence(html,{"source_url":"https://www.york.ca/projects/reservoir"})
    assert result["document_links_count"]==2
    assert json.loads(result["official_pdf_urls_json"]) == ["https://www.york.ca/reports/study.pdf"]


def test_pdf_evidence_with_mock_reader(monkeypatch):
    fake = SimpleNamespace(is_encrypted=False,pages=[
        SimpleNamespace(extract_text=lambda:(
          "The preliminary design for the reservoir expansion is ongoing. "
          "The estimated capital cost is $34 million for this major construction project. "
          "Environmental assessment is expected before detailed design. "
          "This report is published by the regional authority."))])
    monkeypatch.setattr(mod,"PdfReader",lambda fp,strict:fake)
    value=mod._evidence(b"%PDF-1.7\nsynthetic")
    assert "$34 million" in value["budget_evidence"]
    assert value["stage_evidence"]=="DESIGN_OR_TENDER"
    assert value["text_pages"]==1


def test_document_baseline_and_repeat_and_changed(tmp_path,monkeypatch):
    seed(tmp_path)
    def fake_extract(raw):
        return {"evidence_excerpt":raw.decode("latin1"),
                "budget_evidence":"","stage_evidence":"ASSESSMENT","text_pages":2}
    monkeypatch.setattr(mod,"_evidence",fake_extract)
    one=mod.run(tmp_path,today=dt.date(2026,11,4),fetcher=lambda u:b"%PDF-1.7\nfirst")
    assert one["selected_pdf_links"]==3
    assert one["documents_with_text"]==3
    assert one["new_or_changed"]==0
    two=mod.run(tmp_path,today=dt.date(2026,11,5),fetcher=lambda u:b"%PDF-1.7\nfirst")
    assert two["new_or_changed"]==0
    three=mod.run(tmp_path,today=dt.date(2026,11,6),
        fetcher=lambda u:b"%PDF-1.7\nsecond" if u.endswith("pumps.pdf") else b"%PDF-1.7\nfirst")
    assert three["new_or_changed"]==1
    assert three["verified_procurement_opportunities"]==0
    with (tmp_path/mod.CHANGES).open(encoding="utf-8-sig") as fp:
        changed=list(csv.DictReader(fp))
    assert changed[0]["authority"]=="Peel"
    assert changed[0]["first_seen_local"]=="2026-11-04"


def test_policy_failure_is_reported_without_destroying_other_evidence(tmp_path,monkeypatch):
    seed(tmp_path)
    monkeypatch.setattr(mod,"_evidence",lambda raw:{
        "evidence_excerpt":"Wastewater pumping expansion under study",
        "budget_evidence":"","stage_evidence":"ASSESSMENT","text_pages":1})
    def fetch(url):
        if "pumps.pdf" in url: raise ValueError("PDF_POLICY_DENIED:robots")
        return b"%PDF-1.7\n"
    result=mod.run(tmp_path,fetcher=fetch)
    assert result["documents_with_text"]==2
    assert result["failed_documents"]==1
    assert result["failures"][0]["authority"]=="Peel"


def test_fake_pdf_and_scanned_pdf_not_accepted(monkeypatch):
    import pytest
    with pytest.raises(ValueError,match="INVALID_BOUNDED_PDF"):
        mod._evidence(b"<html>Not a PDF</html>")
    fake=SimpleNamespace(is_encrypted=False,pages=[
        SimpleNamespace(extract_text=lambda:"")])
    monkeypatch.setattr(mod,"PdfReader",lambda fp,strict:fake)
    with pytest.raises(ValueError,match="NO_EXTRACTABLE_PDF_TEXT"):
        mod._evidence(b"%PDF-1.4\nscanned")


def test_missing_upstream_is_zero_not_success(tmp_path):
    result=mod.run(tmp_path)
    assert result["status"]=="NO_VERIFIED_PDF_EVIDENCE"
    assert result["selected_pdf_links"]==0
