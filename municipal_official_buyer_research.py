"""Official-source buyer and tender research: collect evidence, not contacts by guess."""
import argparse,datetime as dt,hashlib,json,re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from municipal_meeting_capture import public_https
from municipal_buyer_procurement import PORTALS,dossier
class Visible(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ("script","style","noscript"):self.skip+=1
 def handle_endtag(self,tag):
  if tag in ("script","style","noscript"):self.skip=max(0,self.skip-1)
 def handle_data(self,text):
  if not self.skip:self.parts.append(text)
def retrieve(url):
 if not public_https(url):raise ValueError("Source must be public HTTPS")
 p=urlparse(url)
 allowed=("toronto.ca","brampton.ca","mississauga.ca","canadabuys.canada.ca")
 if not any(p.hostname==d or p.hostname.endswith("."+d) for d in allowed):
  raise ValueError("Only public official procurement/municipal domains enabled")
 with urlopen(Request(url,headers={"User-Agent":"GTARadarEvidenceReview/1.0"}),timeout=15) as f:
  if f.status!=200:raise ValueError("HTTP source unavailable")
  data=f.read(500001)
 if len(data)>500000:raise ValueError("Source exceeds safe cap")
 h=Visible();h.feed(data.decode("utf-8","replace"))
 return " ".join(" ".join(h.parts).split())
def shortlist(address,urls,*,fetch=retrieve):
 words=re.findall(r"[A-Za-z0-9]+",address)
 if len(words)<2:raise ValueError("A specific project street address is required")
 # Match the whole address phrase; matching only Street, Road or Avenue creates false hits.
 phrase=r"\b"+r"\s+".join(re.escape(x) for x in words)+r"\b"
 results=[]
 for url in urls[:8]:
  try:
   body=fetch(url)
   for match in list(re.finditer(phrase,body,re.I))[:8]:
    quote=body[max(0,match.start()-160):min(len(body),match.end()+160)]
    results.append({"source_url":url,"quote":quote,"location":"web_excerpt",
      "address":address,"classification":"ADDRESS_MENTION_UNVERIFIED",
      "buyer_verified":False,"contract_open_verified":False,
      "source_page_sha256":hashlib.sha256(body.encode()).hexdigest()})
  except Exception as exc:
   results.append({"source_url":url,"status":"UNAVAILABLE",
                   "reason":type(exc).__name__})
 return {"address":address,"observations":results,
   "verified_contacts":0,"verified_unawarded_contracts":0,
   "checked_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--address",required=True);p.add_argument("--url",action="append",default=[])
 p.add_argument("--out",required=True)
 a=p.parse_args();r=shortlist(a.address,a.url or list(PORTALS.values()))
 f=Path(a.out);f.parent.mkdir(parents=True,exist_ok=True)
 f.write_text(json.dumps(r,indent=2),encoding="utf-8")
 print(json.dumps({"source_evidence_candidates":len(r["observations"]),
 "verified_unawarded_contracts":0,"file":str(f)},indent=2))
if __name__=="__main__":main()
