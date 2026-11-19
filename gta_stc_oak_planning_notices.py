"""Current planning notice recovery: St. Catharines and Oakville official sites.

Unlike historical building permits and inaccessible Oakville eSCRIBE calendar,
these notices contain project-specific proposal descriptions, actual file
numbers, dates, and links to publicly described planning material.

Bounded, per-site robots-gated, no portal bypass or mass PDF downloading.
Publisher reuse for commercial resale is NOT established: evidence/research
only and separate from the paid AI/customer lead selection.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from urllib.robotparser import RobotFileParser

STC_ROOT="https://www.stcatharines.ca"
OAK_ROOT="https://www.oakville.ca"
STC_INDEX=STC_ROOT+"/news/public-notices/?page=1"
OAK_INDEX=OAK_ROOT+"/town-hall/news-notices/2026-planning-public-notices-archive/"
INDEXES={"St. Catharines":STC_INDEX,"Oakville":OAK_INDEX}
OUTPUT="GTA_RADAR_STC_OAK_OFFICIAL_PLANNING_NOTICES.csv"
LINKS="GTA_RADAR_STC_OAK_PLANNING_DOCUMENT_PAGES.csv"
STATUS="GTA_RADAR_STC_OAK_PLANNING_NOTICES_STATUS.json"
ROW_FIELDS=("city","file_number","site_address","project_description",
            "published_applicant_not_buyer","notice_issued_date","date_basis",
            "notice_url","notice_title","publisher_reuse_status",
            "project_materials_reference","verified_buyer",
            "verified_open_contract","verified_first_disclosure")
LINK_FIELDS=("city","file_number","notice_url","official_link",
             "anchor_text","link_type","verified_document_downloaded")
MAX_BYTES=1_000_000
MAX_PAGES=3
MAX_NOTICES_PER_CITY=15

STC_FILE=re.compile(r"\b\d{2}\s+\d{5,8}\s+(?:OP|ZA|SP|CD|CO|SU)\b",re.I)
OAK_FILE=re.compile(r"\b(?:OPA\s*|Z\.\s*|24T[-/]\s*|SP\s*)"
                    r"\d{2,6}(?:[.-]\d{1,6}){0,3}(?:/\d{2,6})?\b",re.I)
ADDRESS=re.compile(r"\b\d{1,6}(?:\s*[-/&]\s*\d{1,6})?\s+"
                   r"(?:[A-Za-z][\w.'-]*\s+){0,6}"
                   r"(?:Street|Road|Avenue|Drive|Boulevard|Lane|Crescent|Court|"
                   r"Parkway|Highway|Trail|Line)\b",re.I)
NOTICE_DATE=re.compile(r"(?:This notice (?:was |is )?issued on|"
                       r"This notice is issued on)\s+"
                       r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",re.I)
STC_DATE=re.compile(r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+20\d{2})\b")
OAK_DATE=re.compile(r"\b([A-Za-z]+\s+\d{1,2},?\s+\d{4})\b")

def clean(v,limit=1600):
    return " ".join(str(v or "").split())[:limit]

def permitted_origin(url,city):
    try:p=urlsplit(url)
    except ValueError:return False
    expected=urlsplit(STC_ROOT if city=="St. Catharines" else OAK_ROOT).hostname
    return p.scheme=="https" and p.hostname in (expected,expected.removeprefix("www.")) and not p.username and not p.password

def robots_allowed(url):
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in ("www.stcatharines.ca","stcatharines.ca","www.oakville.ca","oakville.ca"):
        return False
    rules=RobotFileParser()
    rules.set_url("https://"+p.netloc+"/robots.txt")
    try:
        rules.read()
        return bool(rules.can_fetch("GTA-Radar-PublicPlanningNotices/1.0",url))
    except (OSError,ValueError,UnicodeError):return False

def fetch(url,*,opener=urlopen,robots_check=True):
    p=urlsplit(url)
    if not any(permitted_origin(url,city) for city in INDEXES):
        raise PermissionError("UNAPPROVED_NOTICE_ORIGIN")
    if robots_check and not robots_allowed(url):
        raise PermissionError("ROBOTS_DENIED_OR_UNVERIFIED")
    request=Request(url,headers={"User-Agent":"GTA-Radar-PublicPlanningNotices/1.0"})
    with opener(request,timeout=15) as response:
        final=urlsplit(response.geturl())
        if final.scheme!="https" or final.hostname!=p.hostname:
            raise PermissionError("NOTICE_REDIRECT_REQUIRES_SEPARATE_APPROVAL")
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("NOTICE_RESPONSE_TOO_LARGE")
    return raw.decode("utf-8",errors="replace")

class HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text=[];self.links=[];self.active=None;self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.skip+=1
        if tag=="a" and not self.skip:
            self.active={"href":dict(attrs).get("href",""),"parts":[]}
    def handle_data(self,data):
        if self.skip:return
        self.text.append(data)
        if self.active is not None:self.active["parts"].append(data)
    def handle_endtag(self,tag):
        if tag in ("script","style"):
            self.skip=max(0,self.skip-1)
        if tag=="a" and self.active is not None:
            self.links.append((clean(" ".join(self.active["parts"]),250),
                               self.active["href"]))
            self.active=None

def index_urls(html,*,city):
    obj=HTML();obj.feed(html)
    found=[];seen=set()
    for title,link in obj.links:
        absolute=urljoin(INDEXES[city],link)
        path=urlsplit(absolute).path.lower()
        if city=="St. Catharines":
            valid=("/news/posts/" in path and
                   bool(re.search(r"notice|application|hearing",title,re.I)))
        else:
            valid=("/2026-planning-public-notices-archive/" in path and
                   bool(re.search(r"notice|application|meeting",title,re.I)))
        if not valid or not permitted_origin(absolute,city) or absolute in seen:
            continue
        seen.add(absolute);found.append((title,absolute))
        if len(found)>=MAX_NOTICES_PER_CITY:break
    return found

def date_str(value):
    try:
        return dt.datetime.strptime(value.replace(",",""),"%B %d %Y").date().isoformat()
    except ValueError:
        try:return dt.datetime.strptime(value.replace(",",""),"%b %d %Y").date().isoformat()
        except ValueError:return ""

def parse_notice(html,*,city,title,url):
    if not permitted_origin(url,city):raise ValueError("UNTRUSTED_NOTICE_URL")
    obj=HTML();obj.feed(html)
    text=clean(" ".join(obj.text),15000)
    finder=STC_FILE if city=="St. Catharines" else OAK_FILE
    file_numbers=list(dict.fromkeys(clean(m.group(),130) for m in finder.finditer(text)))
    # A public hearing may discuss policy and contain no project-specific
    # identifier. Do not invent a file ID from an address or a GIS OBJECTID.
    if not file_numbers:
        return [],[]
    site=re.search(r"(?:Site location:|property at|lands located at|for lands located at)\s*"
                   r"([^.;]{8,210})",text,re.I)
    address=clean(site.group(1),220) if site else ""
    if address:
        address=address.split(" The subject lands")[0].split(" Located in ")[0]
    addr_match=ADDRESS.search(address or title+" "+text[:600])
    address=clean(addr_match.group(),210) if addr_match else ""
    if not address:return [],[]
    if city=="Oakville":
        applicant=re.search(r"\bApplicant:\s*(.+?)\s+File number:",text,re.I)
        scope=re.search(r"(?:## )?What is proposed\?\s*(.+?)\s*(?:How to participate|Read the staff report|Review the supporting material)",text,re.I)
    else:
        applicant=None
        scope=re.search(r"(?:PROPOSAL|The Applicant is seeking)\s*(.+?)\s*(?:MORE INFORMATION|The Open House|LEGAL NOTICE|CONTACT)",text,re.I)
    details=clean(scope.group(1),1500) if scope else clean(text[:1200],1200)
    notice_date=NOTICE_DATE.search(text)
    # St Catharines' date is often a standalone publication banner such
    # as '- Nov 10, 2026'. Avoid deriving publication from meeting dates.
    issued=date_str(notice_date.group(1)) if notice_date else ""
    refs=[]
    for name,href in obj.links:
        target=urljoin(url,href)
        if not permitted_origin(target,city):continue
        lower=(name+" "+urlsplit(target).path).lower()
        if any(t in lower for t in ("project webpage","development application","supporting material","study","report","site plan",".pdf")):
            refs.append({"city":city,"file_number":file_numbers[0],
                "notice_url":url,"official_link":target,"anchor_text":name,
                "link_type":"OFFICIAL_REFERENCED_PAGE_NOT_DOWNLOADED",
                "verified_document_downloaded":"False"})
    rows=[]
    for number in file_numbers[:5]:
        rows.append({"city":city,"file_number":number,"site_address":address,
            "project_description":details,
            "published_applicant_not_buyer":clean(applicant.group(1),200) if applicant else "",
            "notice_issued_date":issued,
            "date_basis":"EXPLICIT_ISSUED_NOTICE" if issued else "NOTICE_DATE_NOT_PARSED",
            "notice_url":url,"notice_title":title,
            "publisher_reuse_status":"PUBLIC_NOTICE_COMMERCIAL_REUSE_NOT_VERIFIED",
            "project_materials_reference":"OFFICIAL_LINKS_INDEXED_ONLY" if refs else "",
            "verified_buyer":"False","verified_open_contract":"False",
            "verified_first_disclosure":"False"})
    return rows,refs

def safe_write(path,fields,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({key:("'"+str(row.get(key) or "") if str(row.get(key) or "").lstrip().startswith(("=","+","-","@","\t","\r"))
                        else str(row.get(key) or "")) for key in fields})

def run(results,*,fetcher=fetch):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    records=[];links=[];states={}
    for city,listing in INDEXES.items():
        pages=MAX_PAGES if city=="St. Catharines" else 1
        candidates=[];failures=[]
        for page in range(1,pages+1):
            url=listing.replace("?page=1","?page="+str(page)) if page>1 else listing
            try:
                candidates.extend(index_urls(fetcher(url),city=city))
            except (OSError,PermissionError,ValueError,UnicodeError) as e:
                failures.append("INDEX:"+type(e).__name__+":"+str(e)[:100])
                break
        seen=set();visited=0;recovered=0
        for title,url in candidates:
            if url in seen or visited>=MAX_NOTICES_PER_CITY:continue
            seen.add(url);visited+=1
            try:
                data,refs=parse_notice(fetcher(url),city=city,title=title,url=url)
                records.extend(data);links.extend(refs);recovered+=len(data)
            except (OSError,PermissionError,ValueError,UnicodeError) as e:
                failures.append("NOTICE:"+type(e).__name__+":"+str(e)[:100])
        states[city]={"status":("VALID_EXACT_PLANNING_FILES_PARTIAL" if recovered
                    else "NO_APPLICATION_FILES_OR_SOURCE_FAILED"),
            "notices_examined":visited,"file_ids_found":recovered,
            "failures":failures[:8],"coverage_complete":False,
            "commercial_reuse_verified":False}
    unique={}
    for record in records:
        key=(record["city"],record["file_number"].upper().replace(" ",""))
        unique.setdefault(key,record)
    safe_write(root/OUTPUT,ROW_FIELDS,unique.values())
    safe_write(root/LINKS,LINK_FIELDS,links)
    status={"status":"PUBLIC_NOTICE_RECOVERY_RESEARCH_ONLY",
        "source_status":states,"validated_official_file_records":len(unique),
        "reusable_commercial_records_cleared":0,
        "true_council_agendas_retrieved":0,
        "buyer_verified":0,"first_original_publications_verified":0,
        "paid_ai_calls":0,"outputs":[OUTPUT,LINKS,STATUS]}
    (root/STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    print(json.dumps(run(p.parse_args().results),indent=2))
