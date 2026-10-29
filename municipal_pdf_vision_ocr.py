"""Opt-in DeepSeek vision OCR for image-only municipal PDF pages.

Renders locally with PyMuPDF, no HTTP downloads, conservatively reserves
against existing GTA Radar AI ledger, and never asserts OCR was verified.
"""
from __future__ import annotations
import argparse,base64,csv,datetime as dt,hashlib,json
from pathlib import Path
import v5_investigator as v5
import v8_deepseek_native as native
from toronto_tmmis_documents import extract_local_pdf

OCR_PROMPT=("Transcribe all clearly visible text from this municipal PDF page. "
            "Preserve headings, addresses, application numbers, numerical values "
            "and table relationships as faithfully as possible. "
            "If unreadable write [UNREADABLE]. Never invent missing letters, "
            "names, values or decisions. Output plain text only.")
RESERVE_USD=0.04
STAGE="municipal_page_vision_ocr_v1"

def render_image(pdf,page,dpi=115):
    try:import fitz
    except ImportError as exc:raise RuntimeError("Install PDF renderer: py -3 -m pip install pymupdf") from exc
    with fitz.open(str(pdf)) as d:
        pix=d[page-1].get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),
                                 colorspace=fitz.csRGB,alpha=False)
        # Limit unexpectedly huge pages before base64 API upload.
        data=pix.tobytes("png")
        if len(data)>2_000_000:raise ValueError("Rendered page exceeds 2MB upload limit")
        return "data:image/png;base64,"+base64.b64encode(data).decode("ascii")

def deepseek_ocr(image_data,key,transport=None):
    response=native.request("/chat/completions",{
        "model":"deepseek-flash","thinking":{"type":"disabled"},
        "messages":[{"role":"system","content":OCR_PROMPT},
                    {"role":"user","content":[
                        {"type":"text","text":"Transcribe this one PDF page."},
                        {"type":"image_url","image_url":{"url":image_data,"detail":"high"}}]}],
        "max_tokens":3000,"stream":False},key,transport=transport)
    choice=response["choices"][0]
    if choice.get("finish_reason")=="length":raise ValueError("Vision OCR response truncated")
    value=str(choice["message"].get("content") or "").strip()
    if not value:raise ValueError("Empty vision OCR response")
    return value

def run(pdf,source_url,results,out,*,paid=False,max_pages=2,key=None,
        transport=None,renderer=None):
    if not native.safe_url(source_url):raise ValueError("Original public HTTPS source URL required")
    document=extract_local_pdf(pdf)
    all_pages=[p["page"] for p in document["pages"] if not p["text_present"]]
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    report={"status":"PREFLIGHT","source_url":source_url,"pdf_sha256":document["sha256"],
            "unreadable_pages":all_pages,"ocr_attempted":0,"ocr_succeeded":0,
            "remaining_pages":len(all_pages),"paid_ai_requests":0,
            "verified_projects":0,"verified_buyers":0}
    if not paid:
        (out/"PDF_OCR_COVERAGE.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        return report
    root=Path(results)
    if not root.is_dir():raise ValueError("Existing GTA_RADAR_RESULTS folder required")
    key=v5.key_from_windows() if key is None else key
    if not key:return {**report,"status":"MISSING_API_KEY"}
    db=v5._ledger(root/"v5_ai_budget.sqlite")
    rows=[];failures=[]
    day=dt.date.today().isoformat()
    try:
        for page in all_pages[:max(0,min(int(max_pages),5))]:
            claim="pdf_vision_"+hashlib.sha256((STAGE+document["sha256"]+
                    source_url+str(page)).encode()).hexdigest()[:24]
            legacy=v5._legacy_reserved(root/"deepseek_budget.sqlite",day)
            if not native.ledger_claim(db,day,claim,RESERVE_USD,legacy,daily_limit=0.25):
                failures.append({"page":page,"status":"BUDGET_OR_DUPLICATE_BLOCKED"});break
            report["ocr_attempted"]+=1;report["paid_ai_requests"]+=1
            try:
                image=(renderer or render_image)(pdf,page)
                text=deepseek_ocr(image,key,transport)
                native.ledger_finish(db,day,claim,"UNKNOWN")
                rows.append({"page":page,"text":text,"source_url":source_url,
                    "verification_status":"UNVERIFIED_VISION_OCR"})
                report["ocr_succeeded"]+=1
            except Exception as exc:
                native.ledger_finish(db,day,claim,"UNKNOWN")
                failures.append({"page":page,"status":"FAILED_"+type(exc).__name__})
                break
    finally:db.close()
    # CSV can feed the same text-understanding stage with original page IDs.
    csv_path=out/"PDF_OCR_PAGES.csv"
    with csv_path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["page","text","source_url","verification_status"])
        writer.writeheader();writer.writerows(rows)
    report["remaining_pages"]=len(all_pages)-len(rows)
    report["status"]="OCR_REVIEW_ONLY_COMPLETE" if not report["remaining_pages"] and not failures else "OCR_INCOMPLETE_REVIEW"
    (out/"PDF_OCR_COVERAGE.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    (out/"PDF_OCR_FAILURES.json").write_text(json.dumps(failures,indent=2),encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser()
    for name in ("pdf","source-url","results","out"):p.add_argument("--"+name,required=True)
    p.add_argument("--paid",action="store_true")
    p.add_argument("--max-pages",type=int,default=2)
    a=p.parse_args()
    print(json.dumps(run(a.pdf,a.source_url,a.results,a.out,paid=a.paid,
                          max_pages=a.max_pages),indent=2))
if __name__=="__main__":main()
