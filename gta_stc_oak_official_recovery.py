"""Official St. Catharines permit and Oakville civic publication recovery.

St. Catharines: nightly official Niagara Open Data / City permits FeatureServer.
Oakville: official Town agenda landing and news-notices discovery, with secure
TLS validation diagnostics for Town-hosted source. Existing planning source
is untouched. A civic notice is NOT an eSCRIBE meeting agenda.

All endpoints are separately robots/HTTPS/host gated. TLS verify stays ON.
No proxy, impersonation, authentication or certificate-verify disable.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
import ssl
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request,urlopen
from urllib.robotparser import RobotFileParser

STC="https://services6.arcgis.com/Yx1h0qHJ9wIpQWuU/arcgis/rest/services/Building_Permits_Public/FeatureServer/0"
OAK_MEETINGS="https://www.oakville.ca/town-hall/mayor-council-administration/agendas-meetings/"
OAK_NEWS="https://www.oakville.ca/town-hall/news-notices/"
SOURCES={"St_Catharines_Permits":STC,"Oakville_Meeting_Landing":OAK_MEETINGS,
         "Oakville_Civic_Notices":OAK_NEWS}
FIELDS=("city","record_kind","application_id","address","scope","status",
        "source_date","date_basis","source_url","source_lane","licence",
        "record_note","buyer_verified","first_publication_verified")
DOC_FIELDS=("city","title","official_url","kind","source_landing",
            "meeting_agenda_verified","public_notice_only")
STATUS="GTA_RADAR_STC_OAK_OFFICIAL_RECOVERY_STATUS.json"
OUTPUT="GTA_RADAR_STC_OAK_OFFICIAL_RECORDS.csv"
LINKS="GTA_RADAR_OAKVILLE_CIVIC_LINKS.csv"
PAGE=200
PAGE_CAP=5
MAX_BYTES=2_000_000

def clean(value,n=900):
    return " ".join(str(value or "").split())[:n]

def iso(value):
    if isinstance(value,(int,float)) and 10**11<value<10**14:
        try:return dt.datetime.fromtimestamp(value/1000,dt.timezone.utc).date().isoformat()
        except (OverflowError,ValueError,OSError):pass
    return ""

def source_url_ok(url):
    p=urlsplit(url)
    return (p.scheme=="https" and p.hostname in (
        "services6.arcgis.com","www.oakville.ca","oakville.ca",
        "pub-oakville.escribemeetings.com") and not p.username and not p.password)

def robots_ok(url):
    if not source_url_ok(url):return False
    p=urlsplit(url)
    parser=RobotFileParser()
    parser.set_url(f"https://{p.netloc}/robots.txt")
    try:
        parser.read()
        return bool(parser.can_fetch("GTA-Radar-PublicMunicipalData/1.0",url))
    except (OSError,ValueError,UnicodeError):
        return False

def secure_fetch(url,*,opener=urlopen,check_robots=True,ca_context=None):
    if not source_url_ok(url):raise ValueError("UNAPPROVED_OFFICIAL_SOURCE")
    if check_robots and not robots_ok(url):
        raise PermissionError("ROBOTS_DENIED_OR_UNVERIFIED")
    headers={"User-Agent":"GTA-Radar-PublicMunicipalData/1.0"}
    req=Request(url,headers=headers)
    options={"timeout":16}
    if ca_context is not None:
        options["context"]=ca_context
    with opener(req,**options) as response:
        final=urlsplit(response.geturl())
        origin=urlsplit(url)
        if final.scheme!="https" or final.hostname!=origin.hostname:
            raise PermissionError("CROSS_ORIGIN_REDIRECT_DISALLOWED")
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("SOURCE_RESPONSE_TOO_LARGE")
    return raw.decode("utf-8",errors="replace")

def secure_ca_bundle():
    """Optional CA-store diagnostic. Never return unverified SSL context."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError,OSError,ssl.SSLError):
        return None

def retrieve(source,*,fetcher=secure_fetch):
    try:
        return fetcher(source),"SYSTEM_TRUST_STORE",None
    except ssl.SSLCertVerificationError as e:
        ca=secure_ca_bundle()
        if ca is None:
            raise
        try:
            return fetcher(source,ca_context=ca),"CERTIFI_VALIDATED_CA_BUNDLE","SYSTEM_TLS_CERTIFICATE_VERIFICATION_FAILURE"
        except (OSError,ValueError,PermissionError):
            raise e

def permit_records(*,fetcher=secure_fetch,max_pages=PAGE_CAP):
    if not 1<=max_pages<=PAGE_CAP:raise ValueError("INVALID_CAP")
    metadata=json.loads(fetcher(STC+"?f=json"))
    oid=metadata.get("objectIdField")
    fields={f.get("name") for f in metadata.get("fields",[]) if isinstance(f,dict)}
    if oid not in fields or not isinstance(oid,str):
        raise ValueError("INVALID_PERMIT_SCHEMA_OBJECTID")
    seen=set();rows=[];complete=False
    for page in range(max_pages):
        url=STC+"/query?"+urlencode({"f":"json","where":"1=1",
            "outFields":"*","returnGeometry":"false","orderByFields":oid+" ASC",
            "resultOffset":page*PAGE,"resultRecordCount":PAGE})
        payload=json.loads(fetcher(url))
        features=payload.get("features")
        if payload.get("error") or not isinstance(features,list) or len(features)>PAGE:
            raise ValueError("INVALID_PERMIT_PAGE")
        for feature in features:
            a=feature.get("attributes") if isinstance(feature,dict) else None
            if not isinstance(a,dict) or a.get(oid) is None or a[oid] in seen:
                raise ValueError("DUPLICATE_OR_MISSING_PERMIT_OBJECTID")
            seen.add(a[oid])
            year=a.get("FOLDERYEAR")
            sequence=a.get("FOLDERSEQUENCE")
            folder=clean(a.get("FOLDERDESC"),30)
            # FOLDERYEAR + FOLDERSEQUENCE is an official permit folder
            # reference; OBJECTID0 is only a GIS internal row ID.
            if (not isinstance(year,int) or not isinstance(sequence,int)
                    or not 1900<=year<=2100 or sequence<0):
                continue
            ident=f"{year}-{sequence:06d}"+("-"+folder if folder else "")
            address=clean(a.get("PROPERTYNAME"),220)
            if not address:
                address=clean(" ".join(filter(None,(str(a.get("PROPSTREET") or ""),
                    str(a.get("PROPSTREETTYPE") or "")))),200)
            description=clean(a.get("FOLDERDESCRIPTION"),1000)
            if not address or not description:continue
            rows.append({"city":"St. Catharines","record_kind":"HISTORICAL_OR_ISSUED_PERMIT",
                "application_id":ident,"address":address,"scope":description,
                "status":clean(a.get("STATUSDESC"),100),
                "source_date":iso(a.get("ISSUEDATE") or a.get("INDATE")),
                "date_basis":"ISSUE_OR_INTAKE_DATE_NOT_PUBLICATION",
                "source_url":STC,"source_lane":"STC_NIAGARA_OPEN_DATA_BUILDING_PERMITS",
                "licence":"ST_CATHARINES_OPEN_GOVERNMENT_LICENSE_2_0",
                "record_note":"Permit history; no evidence of available supplier work",
                "buyer_verified":"False","first_publication_verified":"False"})
        if len(features)<PAGE:
            complete=True
            break
    return rows,{"features_examined":len(seen),"permit_ids":len(rows),
                 "pagination_complete":complete,"row_cap":PAGE*max_pages}

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active=None;self.items=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.active={"href":dict(attrs).get("href",""),"text":[]}
    def handle_data(self,data):
        if self.active is not None:self.active["text"].append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.active is not None:
            self.items.append((clean(" ".join(self.active["text"]),200),
                               self.active["href"]))
            self.active=None

KEYWORDS=re.compile(r"\b(?:planning|development|notices?|applications?|council|agendas?|minutes|"
                    r"zoning|industrial|business|meetings?|public hearing)\b",re.I)

def oakville_links(body,*,landing):
    if landing not in (OAK_NEWS,OAK_MEETINGS) or not isinstance(body,str):
        raise ValueError("INVALID_OAKVILLE_LANDING")
    parser=Anchors();parser.feed(body)
    found=[];seen=set()
    for title,href in parser.items:
        if not KEYWORDS.search(title):continue
        url=urljoin(landing,href)
        if url in seen or not source_url_ok(url):continue
        host=urlsplit(url).hostname
        if host=="pub-oakville.escribemeetings.com":
            # Agenda portal is an indexed link; do NOT assert it was opened,
            # validated or its attachments retrieved.
            kind="OFFICIAL_ESCRIBE_LINK_NOT_VERIFIED"
        elif host in ("www.oakville.ca","oakville.ca"):
            kind="TOWN_PUBLIC_PAGE_NOT_MEETING_CONFIRMED"
        else:continue
        seen.add(url)
        found.append({"city":"Oakville","title":title,"official_url":url,
                      "kind":kind,"source_landing":landing,
                      "meeting_agenda_verified":"False",
                      "public_notice_only":"True"})
        if len(found)>=40:break
    return found

def csv_write(path,fields,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:("'"+str(row.get(k) or "")
                if str(row.get(k) or "").lstrip().startswith(("=","+","-","@","\t","\r"))
                else str(row.get(k) or "")) for k in fields})

def run(results,*,permit_collector=permit_records,landing_fetch=retrieve):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    state={};permits=[];links=[]
    try:
        permits,health=permit_collector()
        state["St_Catharines_Permits"]={"status":"LIVE_PERMIT_IDS_PARTIAL" if permits
            else "FETCHED_ZERO_VALID_PERMITS",**health}
    except (OSError,ValueError,PermissionError,TypeError,UnicodeError) as e:
        state["St_Catharines_Permits"]={"status":"BLOCKED_OR_FAILED",
            "reason":type(e).__name__+":"+str(e)[:180],"permit_ids":0}
    for lane,url in (("Oakville_Meeting_Landing",OAK_MEETINGS),
                     ("Oakville_Civic_Notices",OAK_NEWS)):
        try:
            body,trust,previous=landing_fetch(url)
            items=oakville_links(body,landing=url)
            links.extend(items)
            state[lane]={"status":"OFFICIAL_LINKS_DISCOVERED_NOT_AGENDAS" if items
                         else "SOURCE_FETCHED_ZERO_RELEVANT_LINKS",
                         "link_count":len(items),"verified_agendas":0,
                         "tls_trust_validation":trust,
                         "system_certificate_problem":previous or ""}
        except (OSError,ValueError,PermissionError,TypeError,UnicodeError) as e:
            state[lane]={"status":"BLOCKED_OR_FAILED",
                "reason":type(e).__name__+":"+str(e)[:180],
                "link_count":0,"verified_agendas":0}
    csv_write(root/OUTPUT,FIELDS,permits)
    csv_write(root/LINKS,DOC_FIELDS,links)
    result={"status":"OFFICIAL_STC_OAK_RECOVERY_DIAGNOSTIC",
        "sources":state,"stc_permit_ids":len(permits),
        "oakville_official_links_unverified_as_agendas":len(links),
        "oakville_actual_agendas_retrieved":0,
        "stc_permits_are_new_planning_applications":False,
        "verified_first_publications":0,"verified_buyers":0,
        "verified_open_supplier_work":0,"paid_ai_calls":0,
        "original_oakville_planning_collection_preserved":True,
        "outputs":[OUTPUT,LINKS,STATUS]}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--results",required=True)
    print(json.dumps(run(parser.parse_args().results),indent=2))
