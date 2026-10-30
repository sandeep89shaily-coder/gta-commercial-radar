"""Local-first municipal meeting transcription, review-only.

No video downloads, no paid API, no automatic publication. Only accepts an
existing local media file and a public original meeting URL for citations.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re
from pathlib import Path
from urllib.parse import urlparse

TERMS=("site plan","industrial","warehouse","factory","manufacturing",
       "data centre","data center","mechanical contractor","hvac","cooling",
       "construction","planning application","developer","procurement",
       "tender","request for proposal","expansion","rezoning","equipment")

def public_url(url):
    try:
        p=urlparse(url)
        return p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:return False

def label_segments(segments,terms=TERMS):
    out=[]
    for n,seg in enumerate(segments,1):
        value=str(seg.get("text") or "").strip()
        if not value:continue
        matches=[term for term in terms if re.search(r"(?<!\w)"+re.escape(term)+r"(?!\w)",value,re.I)]
        start=float(seg["start"]);end=float(seg["end"])
        if start<0 or end<start:raise ValueError("Invalid audio timestamp")
        out.append({"segment":n,"start_seconds":round(start,2),"end_seconds":round(end,2),
                    "transcript":value,"candidate_terms":";".join(matches),
                    "review_required":bool(matches)})
    return out

def transcribe_file(media,meeting_url,out,*,model="small",device="cpu",compute_type="int8",
                    language="en",engine=None,max_bytes=2_000_000_000):
    media=Path(media).expanduser().resolve()
    if not media.is_file():raise FileNotFoundError("Local recording not found")
    if media.stat().st_size>max_bytes:raise ValueError("Recording over size limit")
    if not public_url(meeting_url):raise ValueError("An original HTTPS meeting URL is required")
    if engine is None:
        try:from faster_whisper import WhisperModel
        except ImportError as e:raise RuntimeError("Install local transcription dependency: pip install faster-whisper") from e
        engine=WhisperModel(model,device=device,compute_type=compute_type)
    segments,info=engine.transcribe(str(media),language=language,
                  vad_filter=True,beam_size=5,condition_on_previous_text=False)
    rows=label_segments({"start":s.start,"end":s.end,"text":s.text} for s in segments)
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    hasher=hashlib.sha256()
    with media.open("rb") as source:
        for block in iter(lambda:source.read(4*1024*1024),b""):
            hasher.update(block)
    digest=hasher.hexdigest()
    for row in rows:
        row["meeting_url"]=meeting_url
        row["recording_sha256"]=digest
        row["verification_status"]="UNVERIFIED_SPEECH_TO_TEXT"
    fields=["segment","start_seconds","end_seconds","transcript","candidate_terms",
            "review_required","meeting_url","recording_sha256","verification_status"]
    with (out/"MEETING_TRANSCRIPT.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    manifest={"status":"TRANSCRIBED_REVIEW_ONLY","media_file":str(media),"meeting_url":meeting_url,
        "recording_sha256":digest,"segments":len(rows),
        "segments_flagged":sum(x["review_required"] for x in rows),
        "model":model,"device":device,"language":language,
        "paid_api_calls":0,"verified_projects":0,"verified_buyers":0,
        "warning":"Transcription can mishear names/numbers. Flags are keyword leads for listening, not proven events."}
    (out/"MEETING_TRANSCRIPT_MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--media",required=True,help="Existing local authorized audio/video file")
    p.add_argument("--meeting-url",required=True,help="Original public meeting HTTPS URL")
    p.add_argument("--out",required=True)
    p.add_argument("--model",default="small")
    p.add_argument("--device",choices=["cpu","cuda"],default="cpu")
    p.add_argument("--compute-type",default="int8")
    a=p.parse_args()
    print(json.dumps(transcribe_file(a.media,a.meeting_url,a.out,model=a.model,
           device=a.device,compute_type=a.compute_type),indent=2))

if __name__=="__main__":main()
