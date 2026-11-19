"""Official Toronto AIC enrichment for existing CKAN application IDs.

Uses City of Toronto's published ArcGIS AIC layer 60 to fetch details for a
small number of EXACT Toronto CKAN/combined file identifiers. Documents are
discoverable only on an independently robots-permitted official application
page; layer 60 HAS NO attachments. Never infer a drawing is accessible solely
from an AIC_URL, and never guess/download undocumented document APIs.

Not a new municipality, not a first-publication detector, not buyer research.
Runs on the existing daily workspace and writes separate auditable outputs.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

LAYER="https://gis.toronto.ca/arcgis/rest/services/cot_geospatial11/FeatureServer/60"
AIC_BASE="https://www.toronto.ca/city-government/planning-development/application-information-centre/"
CKAN_MASTER="GTA_RADAR_COMBINED_24_CITY_PROJECT_MASTER.csv"
ENRICH="GTA_RADAR_TORONTO_AIC_ENRICHMENT.csv"
DOCUMENTS="GTA_RADAR_TORONTO_AIC_DOCUMENT_INDEX.csv"
STATUS="GTA_RADAR_TORONTO_AIC_ENRICHMENT_STATUS.json"
MAX_PROJECTS=15
MAX_BYTES=2_000_000
DOCUMENT_EXTS=(".pdf",".doc",".docx",".xls",".xlsx")
OUTFIELDS=(
    "OBJECTID","APPLICATION_NUMBER","REFERENCEFILE","FULL_ADDRESS",
    "FOLDERDESCRIPTION","APPLICATION_TYPE","FOLDERTYPE_DESC",
    "STATUS_DESC","LATEST_MILESTONE","LATEST_MILESTONE_DATE",
    "COMMUNITYMEETINGDATE","HEARING_DATE","SUBMIT_DATE",
    "LAST_MODIFIED_DATE","OPENRELATEDFOLDERCOUNT","ASSIGNEDPLANNER",
    "PLANNEREMAIL","AIC_URL"
)
ENRICH_FIELDS=(
    "canonical_id","application_id","address_from_ckan",
    "aic_application_number","aic_address","aic_description",
    "aic_application_type","aic_status","aic_latest_milestone",
    "aic_latest_milestone_date","aic_meeting_date","aic_hearing_date",
    "aic_submit_date_not_first_publication","aic_updated_date_not_first_publication",
    "aic_related_file_count","published_planner_name_not_buyer",
    "published_planner_email_not_buyer","official_aic_application_url",
    "aic_metadata_match_status","aic_document_discovery_status",
    "document_links_discovered","verified_original_publication",
    "verified_buying_contact","verified_open_supplier_work",
)
DOC_FIELDS=("canonical_id","application_id","document_title",
            "official_document_url","discovery_method","document_type",
            "not_verified_procurement_or_first_publication")

def clean(v, cap=1000):
    return " ".join(str(v or "").split())[:cap]

def normalized_id(v):
    return re.sub(r"[^A-Z0-9]","",clean(v).upper())

def iso_date(value):
    if isinstance(value,(int,float)) and 0<value<10**14:
        try:
            return dt.datetime.fromtimestamp(value/1000,dt.timezone.utc).date().isoformat()
        except (ValueError,OSError,OverflowError):
            return ""
    return ""

def approved_url(url,*,kind):
    try:
        p=urlsplit(url)
    except ValueError:
        return ""
    if p.scheme!="https" or not p.hostname or p.username or p.password:
        return ""
    if kind=="aic":
        if p.hostname not in ("toronto.ca","www.toronto.ca"):
            return ""
        if not p.path.lower().startswith(
            "/city-government/planning-development/application-information-centre"):
            return ""
    elif kind=="document":
        if p.hostname not in ("toronto.ca","www.toronto.ca"):
            return ""
        if not p.path.lower().endswith(DOCUMENT_EXTS):
            return ""
    return url

def robots_allowed(url):
    p=urlsplit(url)
    if p.scheme!="https" or not p.hostname:
        return False
    robot=RobotFileParser()
    robot.set_url(f"https://{p.netloc}/robots.txt")
    try:
        robot.read()
        return bool(robot.can_fetch("GTA-Radar-Toronto-AIC-enrichment/1.0",url))
    except (OSError,ValueError,UnicodeError):
        return False

def fetch(url,*,check_robots=True,opener=urlopen):
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in ("gis.toronto.ca","www.toronto.ca","toronto.ca"):
        raise PermissionError("NON_OFFICIAL_SOURCE")
    if p.username or p.password:
        raise PermissionError("EMBEDDED_CREDENTIALS_REJECTED")
    if check_robots and not robots_allowed(url):
        raise PermissionError("SOURCE_ROBOTS_DENIED_OR_UNVERIFIED")
    req=Request(url,headers={"User-Agent":"GTA-Radar-Toronto-AIC-enrichment/1.0"})
    with opener(req,timeout=16) as response:
        final=urlsplit(response.geturl())
        if final.scheme!="https" or final.hostname!=p.hostname:
            raise PermissionError("UNAPPROVED_SOURCE_REDIRECT")
        payload=response.read(MAX_BYTES+1)
    if len(payload)>MAX_BYTES:
        raise ValueError("SOURCE_TOO_LARGE")
    return payload.decode("utf-8",errors="replace")

def select_projects(root,*,max_projects=MAX_PROJECTS):
    if not 1<=max_projects<=MAX_PROJECTS:
        raise ValueError("OUT_OF_RANGE")
    file=Path(root)/CKAN_MASTER
    if not file.is_file() or file.is_symlink() or file.stat().st_size>80_000_000:
        return []
    result=[];seen=set()
    with file.open(encoding="utf-8-sig",newline="") as fp:
        for row in csv.DictReader(fp):
            if (row.get("city")!="Toronto" or
                    row.get("record_kind")!="APPLICATION"):
                continue
            ident=clean(row.get("application_id"),120)
            normalized=normalized_id(ident)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append({
                "canonical_id":row.get("canonical_id",""),
                "application_id":ident,
                "address":clean(row.get("address"),220),
                "scope":clean(row.get("scope"),1800),
            })
            if len(result)==max_projects:
                break
    return result

def query_exact(application_id,*,fetcher=fetch):
    ident=clean(application_id,120)
    if not ident or not normalized_id(ident):
        raise ValueError("EXACT_FILE_NUMBER_REQUIRED")
    # String literal is quoted as ArcGIS SQL text; only official layer and
    # whitelisted columns are queried. No arbitrary WHERE/host can be supplied.
    # AIC strips spaces from application numbers; CKAN may preserve them.
    # Query ONLY these two exact official spellings, never fuzzy LIKE.
    variants=list(dict.fromkeys((ident,normalized_id(ident))))
    where="APPLICATION_NUMBER IN (" + ",".join(
        "'"+v.replace("'","''")+"'" for v in variants) + ")"
    url=LAYER+"/query?"+urlencode({
        "where":where,"outFields":",".join(OUTFIELDS),
        "returnGeometry":"false","f":"json","resultRecordCount":3,
    })
    data=json.loads(fetcher(url))
    if not isinstance(data,dict) or data.get("error"):
        raise ValueError("AIC_ARCGIS_ERROR")
    features=data.get("features")
    if not isinstance(features,list) or len(features)>3:
        raise ValueError("AIC_SCHEMA_OR_RESULT_CAP")
    matched=[]
    for f in features:
        a=f.get("attributes") if isinstance(f,dict) else None
        if not isinstance(a,dict):
            raise ValueError("AIC_INVALID_FEATURE")
        if normalized_id(a.get("APPLICATION_NUMBER"))==normalized_id(ident):
            matched.append(a)
    if len(matched)!=1:
        return None,("NO_EXACT_AIC_MATCH" if not matched else
                     "AMBIGUOUS_AIC_RECORDS")
    return matched[0],"EXACT_AIC_MATCH"

class DocumentLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current=None
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.current={"href":dict(attrs).get("href",""),"text":[]}
    def handle_data(self,data):
        if self.current is not None:
            self.current["text"].append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.current is not None:
            self.links.append((clean(" ".join(self.current["text"]),160),
                               self.current["href"]))
            self.current=None

def document_links(html,*,page_url):
    if not approved_url(page_url,kind="aic"):
        raise ValueError("UNAPPROVED_AIC_PAGE_URL")
    if not isinstance(html,str) or len(html.encode("utf-8"))>MAX_BYTES:
        raise ValueError("INVALID_AIC_HTML")
    parser=DocumentLinks();parser.feed(html)
    results=[];seen=set()
    for title,href in parser.links:
        url=approved_url(urljoin(page_url,href),kind="document")
        if not url or url in seen:
            continue
        seen.add(url)
        results.append({"document_title":title or "Official AIC linked document",
                        "official_document_url":url,
                        "discovery_method":"LINK_ON_PERMITTED_OFFICIAL_AIC_HTML",
                        "document_type":urlsplit(url).path.rsplit(".",1)[-1].lower(),
                        "not_verified_procurement_or_first_publication":"True"})
        if len(results)>=30:
            break
    return results

def make_record(project,attributes,state):
    a=attributes or {}
    link=approved_url(clean(a.get("AIC_URL"),1000),kind="aic")
    return {
        "canonical_id":project["canonical_id"],
        "application_id":project["application_id"],
        "address_from_ckan":project["address"],
        "aic_application_number":clean(a.get("APPLICATION_NUMBER"),120),
        "aic_address":clean(a.get("FULL_ADDRESS"),230),
        "aic_description":clean(a.get("FOLDERDESCRIPTION"),2400),
        "aic_application_type":clean(a.get("APPLICATION_TYPE") or a.get("FOLDERTYPE_DESC"),150),
        "aic_status":clean(a.get("STATUS_DESC"),150),
        "aic_latest_milestone":clean(a.get("LATEST_MILESTONE"),150),
        "aic_latest_milestone_date":iso_date(a.get("LATEST_MILESTONE_DATE")),
        "aic_meeting_date":iso_date(a.get("COMMUNITYMEETINGDATE")),
        "aic_hearing_date":iso_date(a.get("HEARING_DATE")),
        "aic_submit_date_not_first_publication":iso_date(a.get("SUBMIT_DATE")),
        "aic_updated_date_not_first_publication":iso_date(a.get("LAST_MODIFIED_DATE")),
        "aic_related_file_count":clean(a.get("OPENRELATEDFOLDERCOUNT"),140),
        "published_planner_name_not_buyer":clean(a.get("ASSIGNEDPLANNER"),130),
        "published_planner_email_not_buyer":clean(a.get("PLANNEREMAIL"),200),
        "official_aic_application_url":link,
        "aic_metadata_match_status":state,
        "aic_document_discovery_status":"NOT_ATTEMPTED",
        "document_links_discovered":"0",
        "verified_original_publication":"False",
        "verified_buying_contact":"False",
        "verified_open_supplier_work":"False",
    }

def write_csv(path,fields,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k:("'"+str(row.get(k) or "")
                if str(row.get(k) or "").lstrip().startswith(("=","+","-","@","\t","\r"))
                else str(row.get(k) or "")) for k in fields})

def run(results,*,queryer=query_exact,page_fetcher=fetch,
        discover_documents=True,max_projects=MAX_PROJECTS):
    root=Path(results)
    if not root.is_dir():
        raise ValueError("EXISTING_RADAR_RESULTS_REQUIRED")
    projects=select_projects(root,max_projects=max_projects)
    metadata=[];documents=[];failures=[]
    for project in projects:
        try:
            attrs,state=queryer(project["application_id"])
            rec=make_record(project,attrs,state)
            if state=="EXACT_AIC_MATCH":
                page=rec["official_aic_application_url"]
                if not discover_documents:
                    rec["aic_document_discovery_status"]="DOCUMENT_DISCOVERY_DISABLED"
                elif not page:
                    rec["aic_document_discovery_status"]="NO_APPROVED_AIC_APPLICATION_URL"
                else:
                    try:
                        html=page_fetcher(page)
                        links=document_links(html,page_url=page)
                        for doc in links:
                            documents.append({**doc,
                                "canonical_id":project["canonical_id"],
                                "application_id":project["application_id"]})
                        rec["document_links_discovered"]=str(len(links))
                        rec["aic_document_discovery_status"]=(
                            "PUBLIC_OFFICIAL_DOCUMENT_LINKS_INDEXED" if links else
                            "NO_DOCUMENT_LINKS_IN_ACCESSIBLE_HTML")
                    except (OSError,PermissionError,ValueError,UnicodeError) as e:
                        rec["aic_document_discovery_status"]="AIC_PAGE_BLOCKED_OR_UNAVAILABLE"
                        failures.append({"application_id":project["application_id"],
                            "stage":"document_discovery",
                            "reason":type(e).__name__})
            else:
                rec["aic_document_discovery_status"]="AIC_RECORD_NOT_EXACTLY_MATCHED"
            metadata.append(rec)
        except (OSError,PermissionError,ValueError,TypeError,KeyError,UnicodeError) as e:
            failures.append({"application_id":project["application_id"],
                             "stage":"aic_metadata","reason":type(e).__name__})
            metadata.append(make_record(project,None,
                            "AIC_METADATA_BLOCKED_OR_FAILED"))
    write_csv(root/ENRICH,ENRICH_FIELDS,metadata)
    write_csv(root/DOCUMENTS,DOC_FIELDS,documents)
    result={
        "status":"TORONTO_AIC_ENRICHMENT_PARTIAL_NOT_CUSTOMER_RELEASE",
        "input_source":CKAN_MASTER,
        "official_source":LAYER,
        "candidate_application_ids":len(projects),
        "exact_aic_matches":sum(r["aic_metadata_match_status"]=="EXACT_AIC_MATCH" for r in metadata),
        "official_document_links_indexed_not_downloaded":len(documents),
        "records_with_aic_page_blocked":sum(
            r["aic_document_discovery_status"]=="AIC_PAGE_BLOCKED_OR_UNAVAILABLE"
            for r in metadata),
        "aic_document_attachments_in_arcgis":False,
        "unmatched_or_failed_source_count":sum(
            r["aic_metadata_match_status"]!="EXACT_AIC_MATCH" for r in metadata),
        "failure_details":failures[:MAX_PROJECTS*2],
        "publication_dates_verified":0,
        "buyer_contacts_verified":0,
        "supplier_packages_verified_open":0,
        "paid_ai_calls":0,
        "outputs":[ENRICH,DOCUMENTS,STATUS],
        "warning":"AIC URLs are deep links, not proof of publicly downloadable drawings; no undocumented document API or denied access is bypassed.",
    }
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",required=True)
    p.add_argument("--max-projects",type=int,default=MAX_PROJECTS)
    args=p.parse_args()
    print(json.dumps(run(args.results,max_projects=args.max_projects),indent=2))
