"""Compare flagged spoken segments against an already saved municipal PDF.

String overlap is a triage hint ONLY, not semantic verification or a new project.
"""
import argparse,csv,json,re
from pathlib import Path
from toronto_tmmis_documents import extract_local_pdf

def tokens(s):
    return {w for w in re.findall(r"[a-z0-9]+",str(s).lower()) if len(w)>3}

def compare(transcript_csv,pdf,out):
    doc=extract_local_pdf(pdf)
    with Path(transcript_csv).open(newline="",encoding="utf-8-sig") as f:
        lines=list(csv.DictReader(f))
    pages=[(p["page"],tokens(p["text"])) for p in doc["pages"] if p.get("text_present")]
    findings=[]
    for row in lines:
        if str(row.get("review_required","")).lower()!="true":continue
        terms=tokens(row["transcript"])
        overlap=sorted(((len(terms & words)/max(1,len(terms)),n) for n,words in pages),reverse=True)
        score,page=overlap[0] if overlap else (0,None)
        findings.append({"segment":row["segment"],"timestamp_seconds":row["start_seconds"],
          "transcript":row["transcript"],"meeting_url":row["meeting_url"],
          "nearest_pdf_page":page,"token_overlap":round(score,3),
          "pdf_relation":"POSSIBLE_OVERLAP_NOT_FACT_VERIFIED" if score>=.25 else "NOT_FOUND_IN_WRITTEN_REPORT_REVIEW",
          "review_required":True})
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    result={"status":"COMPARISON_FOR_HUMAN_REVIEW","transcribed_mentions":len(findings),
            "pdf_sha256":doc["sha256"],"verified_opportunities":0,"findings":findings}
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--transcript",required=True);p.add_argument("--pdf",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();print(json.dumps(compare(a.transcript,a.pdf,a.out),indent=2))
if __name__=="__main__":main()
