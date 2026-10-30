"""Convert VTT captions to a timestamped review-only transcript CSV."""
import argparse,csv,json,re
from pathlib import Path
def sec(x):
 v=[float(a) for a in x.replace(",",".").split(":")]
 return sum(n*60**i for i,n in enumerate(reversed(v)))
def convert(source,out,url):
 from municipal_meeting_capture import public_https
 if not public_https(url):raise ValueError("HTTPS source required")
 raw=Path(source).read_text(encoding="utf-8-sig").replace("\r\n","\n")
 rows=[]
 for chunk in re.split(r"\n\s*\n",raw):
  lines=[v.strip() for v in chunk.splitlines() if v.strip()]
  line=next((i for i,s in enumerate(lines) if "-->" in s),None)
  if line is None:continue
  left,right=lines[line].split("-->",1)
  text=" ".join(re.sub(r"<[^>]*>","",s) for s in lines[line+1:])
  if not text:continue
  start=sec(left.strip().split()[0]);end=sec(right.strip().split()[0])
  if start>end:continue
  if rows and rows[-1]["transcript"]==text:continue
  rows.append({"start_seconds":start,"end_seconds":end,"transcript":text,
    "meeting_url":url,"verification_status":"UNVERIFIED_CAPTION_TEXT"})
 dst=Path(out);dst.parent.mkdir(parents=True,exist_ok=True)
 with dst.open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=["start_seconds","end_seconds","transcript","meeting_url","verification_status"])
  w.writeheader();w.writerows(rows)
 return {"caption_segments":len(rows),"output":str(dst),"verified":False}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--captions",required=True);p.add_argument("--out",required=True)
 p.add_argument("--url",required=True);a=p.parse_args()
 print(json.dumps(convert(a.captions,a.out,a.url),indent=2))
if __name__=="__main__":main()
