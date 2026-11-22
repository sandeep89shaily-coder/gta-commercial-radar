"""Previously missed live-run PDF audit path is safely recognized offline."""
import csv
import hashlib
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from gta_council_captured_pdf_bridge import review

def test_actual_full_run_pdf_audit_is_examined(tmp_path):
    folder=tmp_path/"TOTAL_INTELLIGENCE_REVIEW"/"MEETING_DOCUMENTS"/"Toronto"
    pdf_folder=folder/"pdfs"
    pdf_folder.mkdir(parents=True)
    pdf=pdf_folder/"example.pdf"
    writer=PdfWriter()
    writer.add_blank_page(width=612,height=792)
    data=BytesIO()
    writer.write(data)
    pdf.write_bytes(data.getvalue())
    url="https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-123456.pdf"
    audit=folder/"COMBINED_PDF_FETCH_AUDIT.csv"
    with audit.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["url","status","sha256","saved_path"])
        w.writeheader()
        w.writerow({"url":url,"status":"CAPTURED",
            "sha256":hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "saved_path":"GTA_RADAR_RESULTS/TOTAL_INTELLIGENCE_REVIEW/MEETING_DOCUMENTS/Toronto/pdfs/example.pdf"})
    result=review(tmp_path)
    assert result["captured_official_pdfs_inspected"]==1
    assert result["documents"][0]["city"]=="Toronto"
    assert result["documents"][0]["status"]=="NO_RELEVANT_EXTRACTABLE_TEXT_HOLD"
    assert result["verified_buyers"]==0
    assert result["network_calls"]==0
