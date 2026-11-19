"""Permitted alternative official feeds for previously blocked municipal lanes.

Kitchener: public, open-licensed Planning_Applications_Active FeatureServer/0.
Caledon: current-applications public HTML index, research-only pending reuse
licence confirmation. No proxy/403/robots bypass; no paid model, no database
changes, no invented project announcement dates or buyer contacts.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urljoin
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

KITCHENER="https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer/0"
CALEDON="https://www.caledon.ca/en/town-services/current-applications"
CITIES=("Kitchener","Caledon")
OUT="GTA_RADAR_ALTERNATIVE_OFFICIAL_APPLICATIONS.csv"
STATUS="GTA_RADAR_ALTERNATIVE_OFFICIAL_STATUS.json"
FIELDS=("city","application_id","address","scope","applicant","stage",
        "category","date","date_basis","source_url","source_lane",
        "source_permission","publication_verified","buyer_verified",
        "open_supplier_package_verified")
MAX_BYTES=2_000_000
MAX_ROWS=300
PAGE=100
FILE=re.compile(r"(?<![A-Z0-9])(?:POPA|SPA|RZ|21CDM|21T|SP)\s*[- ]?\s*(?:\d{4}[-/]\d{3,5}|\d{2}[-/]\d{2,5}[A-Z]?)(?![A-Z0-9])",re.I)
ADDRESS=re.compile(r"\b\d{1,6}\s+(?:[A-Za-z][\w.'-]*\s+){0,6}(?:Road|Street|Avenue|Drive|Boulevard|Highway|Lane|Court|Way|Sideroad|Trail|Crescent)\b",re.I)

def clean(x,cap=500):
    return " ".join(str(x or "").split())[:cap]

def date(x):
    if isinstance(x,(int,float)) and x>1e12:
        try:return dt.datetime.fromtimestamp(x/1000,dt.timezone.utc).date().isoformat()
        except (OverflowError, ValueError, OSError):pass
    return ""

def permitted(url,*,robot_factory=RobotFileParser):
    p=urlsplit(url)
    if p.scheme!="https" or not p.hostname or p.username or p.password:return False
    bot=robot_factory()
    bot.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try:
        bot.read()
        return bot.can_fetch("GTA-Radar-official-open-data/1.0",url)
    except (ValueError,OSError):return False

def fetch(url,*,opener=urlopen,check_robots=True,allowed_hosts=None):
    p=urlsplit(url)
    if p.scheme!="https" or not p.hostname or (allowed_hosts and p.hostname not in allowed_hosts):
        raise ValueError("UNAPPROVED_SOURCE_URL")
    if check_robots and not permitted(url):
        raise PermissionError("ROBOTS_DENIED_OR_UNVERIFIED")
    request=Request(url,headers={"User-Agent":"GTA-Radar-official-open-data/1.0"})
    with opener(request,timeout=15) as response:
        effective=urlsplit(response.geturl())
        if effective.scheme!="https" or effective.hostname!=p.hostname:
            raise PermissionError("UNAPPROVED_REDIRECT")
        payload=response.read(MAX_BYTES+1)
    if len(payload)>MAX_BYTES:raise ValueError("RESPONSE_TOO_LARGE")
    return payload.decode("utf-8",errors="replace")

def arcgis_rows(*,fetcher=fetch,check_robots=True,cap=MAX_ROWS):
    if not 1<=cap<=MAX_ROWS:raise ValueError("CAP_OUT_OF_RANGE")
    rows=[]; seen_oid=set(); stopped=False
    for offset in range(0,cap,PAGE):
        count=min(PAGE,cap-offset)
        url=KITCHENER+"/query?"+urlencode({"f":"json","where":"1=1",
            "outFields":"OBJECTID,APPLICATION_NO,ADDRESS,DESCRIPTION,APPLICANT,STATUS,FOLDERTYPE,INDATE",
            "returnGeometry":"false","orderByFields":"OBJECTID ASC",
            "resultOffset":offset,"resultRecordCount":count})
        raw=fetcher(url,check_robots=check_robots,allowed_hosts={"services1.arcgis.com"})
        data=json.loads(raw)
        if not isinstance(data,dict) or data.get("error") or not isinstance(data.get("features"),list):
            raise ValueError("ARCGIS_INVALID_RESPONSE")
        features=data["features"]
        if len(features)>count:raise ValueError("ARCGIS_PAGE_EXCEEDED")
        for feature in features:
            a=feature.get("attributes") if isinstance(feature,dict) else None
            if not isinstance(a,dict):raise ValueError("ARCGIS_INVALID_FEATURE")
            oid=a.get("OBJECTID")
            if oid is None or oid in seen_oid:raise ValueError("ARCGIS_OBJECTID_MISSING_OR_DUPLICATE")
            seen_oid.add(oid)
            ident=clean(a.get("APPLICATION_NO"),150)
            addr=clean(a.get("ADDRESS"),250)
            scope=clean(a.get("DESCRIPTION") or a.get("FOLDERTYPE"),1300)
            if not ident or not addr or not scope:continue
            rows.append({"city":"Kitchener","application_id":ident,"address":addr,
                "scope":scope,"applicant":clean(a.get("APPLICANT"),250),
                "stage":clean(a.get("STATUS"),150),"category":clean(a.get("FOLDERTYPE"),100),
                "date":date(a.get("INDATE")),
                "date_basis":"APPLICATION_INDATE_NOT_PUBLICATION",
                "source_url":KITCHENER,"source_lane":"KITCHENER_OPEN_DATA_OFFICIAL",
                "source_permission":"PUBLISHED_OPEN_DATA_LICENCE_REUSE",
                "publication_verified":"False","buyer_verified":"False",
                "open_supplier_package_verified":"False"})
        if len(features)<count:
            stopped=True
            break
    return rows,{"features_examined":len(seen_oid),"possibly_truncated":not stopped,
                 "max_requested":cap}

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchor=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.anchor={"href":dict(attrs).get("href",""),"parts":[]}
    def handle_data(self,data):
        if self.anchor is not None:self.anchor["parts"].append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.anchor is not None:
            self.links.append((clean(" ".join(self.anchor["parts"]),1000),
                               self.anchor["href"]))
            self.anchor=None

def caledon_rows(html):
    if not isinstance(html,str) or len(html.encode("utf-8"))>MAX_BYTES:
        raise ValueError("HTML_TOO_LARGE_OR_INVALID")
    links=Links();links.feed(html)
    rows=[];seen=set()
    for title,href in links.links:
        ids=list(dict.fromkeys(m.group().strip() for m in FILE.finditer(title)))
        address=ADDRESS.search(title)
        if not ids or address is None:continue
        parsed=urlsplit(urljoin(CALEDON,href))
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
            continue
        if parsed.hostname not in ("caledon.ca","www.caledon.ca","haveyoursaycaledon.ca"):
            # External source links require their own source contract.
            continue
        key=ids[0].upper().replace(" ","")
        if key in seen:continue
        seen.add(key)
        rows.append({"city":"Caledon","application_id":ids[0],
            "address":address.group().strip(),"scope":title,
            "applicant":"","stage":"CURRENT_INDEX_NOT_PROJECT_STATUS_VERIFIED",
            "category":"PLANNING_APPLICATION","date":"",
            "date_basis":"INDEX_HAS_NO_VERIFIED_PUBLICATION_DATE",
            "source_url":urljoin(CALEDON,href),
            "source_lane":"CALEDON_PUBLIC_CURRENT_APPLICATION_INDEX",
            "source_permission":"PUBLIC_INDEX_RESEARCH_REUSE_NOT_VERIFIED",
            "publication_verified":"False","buyer_verified":"False",
            "open_supplier_package_verified":"False"})
    return rows

def run(results,*,fetcher=fetch):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    cities={};allrows=[]
    for city in CITIES:
        try:
            if city=="Kitchener":
                rows,extra=arcgis_rows(fetcher=fetcher)
            else:
                body=fetcher(CALEDON,allowed_hosts={"www.caledon.ca","caledon.ca"})
                rows=caledon_rows(body)
                extra={"index_only":True,"reused_for_commercial_leads":False}
            allrows.extend(rows)
            cities[city]={"status":"LIVE_EXACT_IDS_PARTIAL" if rows else "SOURCE_FETCHED_ZERO_VALID_IDS",
                "valid_application_rows":len(rows),**extra}
        except (OSError, ValueError, PermissionError, UnicodeError, TypeError) as exc:
            cities[city]={"status":"BLOCKED_OR_FAILED",
                "valid_application_rows":0,
                "error":type(exc).__name__+":"+str(exc)[:160]}
    output=root/OUT
    with output.open("w",encoding="utf-8-sig",newline="") as fp:
        w=csv.DictWriter(fp,fieldnames=FIELDS)
        w.writeheader()
        for r in allrows:
            w.writerow({k:("'"+str(r.get(k) or "") if str(r.get(k) or "").lstrip().startswith(("=","+","-","@","\t","\r")) else str(r.get(k) or "")) for k in FIELDS})
    result={"status":"OFFICIAL_ALTERNATIVE_FEEDS_AUDITED","cities":cities,
       "records_current_run":len(allrows),"verified_original_publications":0,
       "verified_buyers":0,"full_coverage_verified":False,
       "source_permissions_kitchener":"OPEN_DATA_LICENCE",
       "source_permissions_caledon":"RESEARCH_ONLY_UNVERIFIED","csv":OUT}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--results",required=True)
    print(json.dumps(run(p.parse_args().results),indent=2))
