"""Official municipal meeting discovery and permitted recording/caption capture.

Safe by default: collect links only. Actual media/subtitle download requires
--capture and operator attestation of permitted use. No bypass of login, DRM,
robots restrictions, or anti-bot controls.
"""
from __future__ import annotations
import argparse,datetime as dt,hashlib,html,json,re,subprocess,sys
from urllib.error import HTTPError
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.request import Request,urlopen

OFFICIAL={
 "Toronto":"https://www.toronto.ca/city-government/council/council-committee-meetings/watch-toronto-city-council-live/",
 "Brampton":"https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/",
 "Mississauga":"https://www.mississauga.ca/council/council-activities/council-and-committees-calendar/",
 "Hamilton":"https://www.hamilton.ca/city-council/council-committee/council-committee-meetings/meetings-agendas-video",
 "Burlington":"https://www.burlington.ca/en/council-and-city-administration/agendas-and-minutes.aspx",
 "Oakville":"https://www.oakville.ca/town-hall/mayor-council-administration/agendas-meetings/",
 "Vaughan":"https://www.vaughan.ca/council/committees-council-agendas-minutes",
 "Kitchener":"https://www.kitchener.ca/council-and-city-administration/council-and-committee-meetings/",
}
ALLOWED_MEDIA={"youtube.com","www.youtube.com","youtu.be","www.youtube-nocookie.com"}
AGENDAS={"Toronto":"https://www.toronto.ca/city-government/council/council-committee-meetings/",
         "Brampton":"https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/",
         "Mississauga":OFFICIAL["Mississauga"],
         "Hamilton":OFFICIAL["Hamilton"],
         "Burlington":OFFICIAL["Burlington"],
         "Oakville":OFFICIAL["Oakville"],
         "Vaughan":OFFICIAL["Vaughan"],
         "Kitchener":OFFICIAL["Kitchener"]}
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
AGENDA_WORDS=re.compile(r"\b(?:agenda|minutes|report|meeting|planning|committee|application|council)\b",re.I)
NAVIGATION_NOISE=re.compile(r"^(?:skip to (?:main )?content|home|search|about|contact|accessibility|privacy|council|meeting|agenda|minutes|committees?|back to top)$",re.I)
REAL_ITEM=re.compile(r"(?:\.pdf(?:$|\?)|agenda[-_/ ]?(?:package|item|\d{2,})|minutes[-_/ ]?\d{2,}|meeting[-_/ ]?\d{2,}|\b20\d{2}\b|planning report|staff report|development application)",re.I)
# A calendar/index link is not an actual individual agenda/staff-report PDF.
# The Nov 13 source run incorrectly counted Brampton's complaint protocol and
# 2026-27 at-a-glance calendar as agenda documents. Fail closed on those.
NON_DOCUMENT=re.compile(r"(?:at[ -]?a[ -]?glance|calendar|schedule|complaint|protocol|code[ -]?of[ -]?conduct|contact|how[ -]?to|overview|guide|faq)",re.I)
ESCRIBE_DOCUMENT=re.compile(r"^/filestream\.ashx$",re.I)

def eligible_agenda_document(url,label,city):
 p=urlparse(url)
 if not public_https(url):return False
 if NON_DOCUMENT.search(label+" "+p.path):return False
 host=(p.hostname or "").lower()
 if host=="pub-"+city.lower()+".escribemeetings.com" and ESCRIBE_DOCUMENT.fullmatch(p.path):
  from urllib.parse import parse_qs
  query=parse_qs(p.query)
  ids=query.get("DocumentId",query.get("documentid",[]))
  return len(ids)==1 and ids[0].isdigit() and int(ids[0])>0
 # Direct PDF files only. An ordinary municipal link or calendar landing
 # page must not be counted as a staff report or agenda item.
 if not p.path.lower().endswith(".pdf"):return False
 title=label+" "+p.path
 return bool(AGENDA_WORDS.search(title) and
             (re.search(r"\\b20\\d{2}\\b",title) or
              re.search(r"(?:staff[ -]?report|planning[ -]?report|agenda|minutes|committee)",title,re.I)))

class AgendaAnchors(HTMLParser):
 def __init__(self):
  super().__init__();self.href=None;self.label=[];self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=="a":
   self.href=dict(attrs).get("href");self.label=[]
 def handle_data(self,data):
  if self.href is not None:self.label.append(data)
 def handle_endtag(self,tag):
  if tag=="a":
   if self.href:self.links.append((self.href," ".join(self.label).strip()))
   self.href=None;self.label=[]

def _agenda_candidates(markup,city,source):
 """Index links only. Never claim agenda content, posting time or project."""
 index=AgendaAnchors();index.feed(markup)
 expected=urlparse(source).hostname
 seen=set();found=[]
 for raw,label in index.links:
  uri=urljoin(source,html.unescape(raw))
  if not public_https(uri):continue
  host=urlparse(uri).hostname
  if not (host==expected or host=="pub-"+city.lower()+".escribemeetings.com"
          or host=="escribemeetings.com" or host=="www.escribemeetings.com"):
   continue
  if not eligible_agenda_document(uri,label,city):continue
  # An official eSCRIBE PDF can be labelled simply "Agenda". For ordinary
  # direct municipal PDFs, retain a meaningful agenda/report label gate.
  is_escribe=(urlparse(uri).hostname or "").lower()=="pub-"+city.lower()+".escribemeetings.com"
  if not is_escribe and (NAVIGATION_NOISE.fullmatch(label.strip()) or len(label.strip())<8):continue
  if not is_escribe and not AGENDA_WORDS.search(label+" "+urlparse(uri).path):continue
  if uri in seen:continue
  seen.add(uri)
  found.append({"url":uri,"title":label[:180],
                "city":city,"discovery_source":source,
                "status":"OFFICIAL_INDEX_LINK_ONLY_PUBLICATION_DATE_UNKNOWN"})
  if len(found)>=60:break
 return found

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
 try:
  markup=fetch(source)
 except HTTPError as error:
  if error.code != 403:
   raise
  # Publisher denial is not a successful index collection. Keep source
  # diagnostics and an empty evidence set, without bypassing HTTP restrictions.
  return {"city":city,"official_page":source,"discovered":0,
          "meetings":[],"agenda_candidates":[],"agenda_links_discovered":0,
          "official_index_status":"HTTP_403_ACCESS_DENIED",
          "source_access_error":"HTTP 403 Forbidden",
          "documents_retrieved":0,"publication_dates_verified":0,
          "limitations":"Official meeting index access denied. No links or dates verified; request publisher-approved access."}
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
 agenda=_agenda_candidates(markup,city,source)
 return {"city":city,"official_page":source,"discovered":len(videos),
         "meetings":videos,"agenda_candidates":agenda,
         "agenda_links_discovered":len(agenda),"official_index_status":"INDEX_FETCHED_LINK_ONLY",
         "documents_retrieved":0,"publication_dates_verified":0,
         "limitations":"Index links do not prove PDF access, first publication or project identity; dynamically rendered calendar entries may be missed"}

def fetch_html(url):
 if url not in OFFICIAL.values():raise ValueError("Non-allowlisted municipal index")
 # Use normal public web access without bypassing site policies.
 req=Request(url,headers={"User-Agent":"GTARadarResearch/1.0 (public source verification)"})
 with urlopen(req,timeout=15) as f:
  if f.status!=200:raise ValueError("Municipal index unavailable")
  body=f.read(4_000_001)
 if len(body)>4_000_000:raise ValueError("Index too large (4 MB bounded limit)")
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
