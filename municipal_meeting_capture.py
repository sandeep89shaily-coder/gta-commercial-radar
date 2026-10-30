"""Official municipal meeting discovery and permitted recording/caption capture.

Safe by default: collect links only. Actual media/subtitle download requires
--capture and operator attestation of permitted use. No bypass of login, DRM,
robots restrictions, or anti-bot controls.
"""
from __future__ import annotations
import argparse,datetime as dt,hashlib,html,json,re,subprocess,sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.request import Request,urlopen

OFFICIAL={
 "Toronto":"https://www.toronto.ca/city-government/council/council-committee-meetings/watch-toronto-city-council-live/",
 "Brampton":"https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/",
}
ALLOWED_MEDIA={"youtube.com","www.youtube.com","youtu.be","www.youtube-nocookie.com"}
AGENDAS={"Toronto":"https://www.toronto.ca/city-government/council/council-committee-meetings/",
         "Brampton":"https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/"}
def public_https(s):
 p=urlparse(s)
 return p.scheme=="https" and bool(p.hostname) and not p.username and not p.password and p.port in (None,443)

class Links(HTMLParser):
 def __init__(self):super().__init__();self.values=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  for a in ("href","src","data-src"):
   if tag in ("a","iframe","video","source") and d.get(a):
    self.values.append((tag,d[a],d.get("title","")))
def normalize_video(url):
 p=urlparse(url)
 host=p.hostname or ""
 if host not in ALLOWED_MEDIA:return None
 # only individual YouTube recordings, not a channel, search, or live-index
 if host in ("youtu.be",) and re.fullmatch(r"/[\w-]{11}",p.path):
  return "https://www.youtube.com/watch?v="+p.path[1:]
 if p.path=="/watch":
  from urllib.parse import parse_qs
  v=parse_qs(p.query).get("v",[""])[0]
  return "https://www.youtube.com/watch?v="+v if re.fullmatch(r"[\w-]{11}",v) else None
 m=re.fullmatch(r"/(?:embed|live|shorts)/([\w-]{11})",p.path)
 return "https://www.youtube.com/watch?v="+m.group(1) if m else None

def discover(city,*,fetch=None,now=None):
 if city not in OFFICIAL:raise ValueError("Unsupported city; explicitly configure official pages")
 source=OFFICIAL[city];fetch=fetch or fetch_html
 markup=fetch(source)
 parser=Links();parser.feed(markup)
 videos=[];seen=set()
 for tag,raw,title in parser.values:
  link=normalize_video(urljoin(source,html.unescape(raw)))
  if link and link not in seen:
   seen.add(link)
   videos.append({"recording_url":link,"official_discovery_url":source,
                  "agenda_directory_url":AGENDAS[city],
                  "agenda_match":"UNRESOLVED_NEEDS_OFFICIAL_MEETING_ID",
                  "title_hint":title,"city":city,"first_seen_utc":(now or dt.datetime.now(dt.timezone.utc)).isoformat(),
                  "capture_status":"LINK_ONLY_NOT_DOWNLOADED"})
 return {"city":city,"official_page":source,"discovered":len(videos),
         "meetings":videos,"limitations":"Some official pages load embeds dynamically; only official-page links captured"}

def fetch_html(url):
 if url not in OFFICIAL.values():raise ValueError("Non-allowlisted municipal index")
 # Use normal public web access without bypassing site policies.
 req=Request(url,headers={"User-Agent":"GTARadarResearch/1.0 (public source verification)"})
 with urlopen(req,timeout=15) as f:
  if f.status!=200:raise ValueError("Municipal index unavailable")
  body=f.read(1_000_001)
 if len(body)>1_000_000:raise ValueError("Index too large")
 return body.decode("utf-8","replace")

def capture(url,out,*,authorized=False,runner=None):
    """Fail closed: YouTube metadata access does not confer download rights."""
    video=normalize_video(url)
    if not video:raise ValueError("Individual YouTube recording URL required")
    if not authorized:raise PermissionError("Explicit authorization is required")
    target=Path(out);target.mkdir(parents=True,exist_ok=True)
    result={"source_url":video,"status":"PLATFORM_DOWNLOAD_PERMISSION_NOT_VERIFIED",
            "files":[],"media_downloaded":False,"captions_downloaded":False,
            "next":"Use officially downloadable municipal captions or authorized local media"}
    (target/"CAPTURE_AUDIT.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--city",choices=list(OFFICIAL))
 p.add_argument("--recording-url");p.add_argument("--out",required=True)
 p.add_argument("--capture",action="store_true");p.add_argument("--authorized",action="store_true")
 a=p.parse_args()
 if a.city:
  result=discover(a.city)
  out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
  (out/(a.city.upper()+"_MEETINGS.json")).write_text(json.dumps(result,indent=2),encoding="utf-8")
 elif a.recording_url:
  result=capture(a.recording_url,a.out,authorized=a.capture and a.authorized)
 else:p.error("Choose --city or --recording-url")
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
