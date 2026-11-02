"""Early planning-application source monitor for sixteen Southern Ontario cities.

SOURCE CONFIGURATION IS NOT DATA COVERAGE.  Only stable public municipal file
identifiers become candidate records, never verified projects.  A city whose
application records live behind a dynamic GIS portal is marked INDEX_ONLY.
First ingestion establishes a baseline; it cannot create a new lead.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SOURCES = {
    "Toronto":"https://www.toronto.ca/city-government/planning-development/application-information-centre/",
    "Brampton":"https://planning.brampton.ca/CitizenAccess/Default.aspx",
    "Mississauga":"https://www.mississauga.ca/services-and-programs/planning-and-development/development-applications/active-development-applications/",
    "Hamilton":"https://www.hamilton.ca/build-invest-grow/planning-development/planning-applications/where-development-happening-hamilton",
    "Burlington":"https://www.burlington.ca/en/planning-and-development/planning-and-development.aspx",
    "Oakville":"https://www.oakville.ca/business-development/planning-development/active-development-applications/",
    "Vaughan":"https://www.vaughan.ca/residential/building-and-construction/vaughans-planning-process",
    "Kitchener":"https://app2.kitchener.ca/appdocs/GISImages/GIS_Web_External/GIS_Metadata_Open_Data/Planning_Applications_Active.html",
    "Markham":"https://www.markham.ca/economic-development-business/planning-development-services/current-planning-applications-and-agendas",
    "Oshawa":"https://www.oshawa.ca/business-development/planning-and-development/development-applications/",
    "Milton":"https://www.milton.ca/business-development/planning-and-development/development-applications/development-application-notices/",
    "Halton Hills":"https://www.haltonhills.ca/developmentproposalsunderreview",
    "Caledon":"https://www.caledon.ca/en/town-services/development-applications.aspx",
    "Cambridge":"https://www.cambridge.ca/business-building-development/building-planning/current-development-applications/",
    "Waterloo":"https://www.engagewr.ca/development-planning-projects",
    "Guelph":"https://guelph.ca/city-government/planning-and-development/current-development-applications/",
}
# These are official source-page endpoints, NOT confirmed per-file APIs.  The
# collector reports blocked/dynamic sources separately and never invents data.
ID_PATTERN = re.compile(
    r"\b(?:OZ\s*/\s*OPA\s*\d{2}-\d{1,3}(?:\s+W\d+)?|"
    r"OZ\s*\d{2}-\d{1,3}(?:\s+W\d+)?|"
    r"21T-M\s*\d{2}-\d{1,3}|"
    r"30CDM-\d{4,6}|"
    r"(?:S-O|Z|OPA|SP|S|ZBA|DPA|DA)[-/ ]\d{2,4}[-/]\d{1,5}|"
    r"\d{2}T-\d{4,6}/[A-Z]|"
    r"\d{3}-\d{3}/\d{2})\b",re.I)
COMMERCIAL = re.compile(
    r"\b(?:industrial|warehouse|manufactur\w*|distribution|logistics|"
    r"factory|commercial|retail|restaurant|employment|data.cent(?:er|re)|"
    r"office|medical|clinic|self.storage|hotel|mixed.use|mixed.use|"
    r"business.park|storage.facility)\b",re.I)
RESIDENTIAL = re.compile(
    r"\b(?:townhomes?|townhouses?|detached.dwellings?|semi.detached|"
    r"residential.apartment|condominium.tower|residential.units)\b",re.I)
NOISE = re.compile(r"\b(?:cookie|accessibility|privacy|subscribe|newsletter|"
                   r"municipal.calendar|meeting.schedule|procedure.by.law)\b",re.I)
LINK = re.compile(r"(?i)(?:circulated planning|complete application|"
                  r"site.plan|development.application|planning.report|"
                  r"public.meeting|development.proposal)")
ROW_FIELDS = ("project_id","city","application_id","description","source_url",
              "record_source_url","record_source_url_basis","source_record_date",
              "source_record_date_basis","first_seen_local","observation",
              "changed_fields","commercial_fit","verification_required")
LINK_FIELDS = ("city","title","url","index_url","first_seen_local",
               "observation","status","publication_date_verified")
STATE = "GTA_RADAR_EARLY_APPLICATION_SEEN.json"
AUDIT = "GTA_RADAR_EARLY_APPLICATION_SOURCE_STATUS.json"
CANDIDATES = "GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv"
NEW = "GTA_RADAR_EARLY_APPLICATION_NEW_OR_CHANGED.csv"
LINKS = "GTA_RADAR_EARLY_APPLICATION_LINKS.csv"

def _safe(url,official):
    try:
        a,b=urlparse(url),urlparse(official)
        return (a.scheme=="https" and a.hostname==b.hostname and
                a.port in (None,443) and not a.username and not a.password
                and not a.fragment)
    except ValueError:return False

def _fetch(url):
    """Fail closed on redirects and non-HTML, never bypass source restrictions."""
    from robots_policy import evaluate
    from toronto_pdf_download import public_dns
    import socket
    from urllib.request import Request
    user_agent="GTARadarEarlyApplications/1.0"
    host=urlparse(url).hostname
    if not public_dns(host,socket.getaddrinfo):
        raise ValueError("NONPUBLIC_OR_UNAVAILABLE_DNS")
    session=requests.Session()
    session.trust_env=False
    session.headers.update({"User-Agent":user_agent,"Accept":"text/html"})
    allowed,why=evaluate(session,url,user_agent,timeout=10)
    if not allowed:raise ValueError(why)
    with session.get(url,timeout=(6,12),allow_redirects=False,stream=True) as response:
        if response.status_code!=200 or response.url!=url:
            raise ValueError("HTTP_"+str(response.status_code)+"_OR_REDIRECT")
        if "html" not in response.headers.get("Content-Type","").lower():
            raise ValueError("NON_HTML_PUBLIC_INDEX")
        chunks=bytearray()
        for part in response.iter_content(65536):
            chunks.extend(part)
            if len(chunks)>2_000_000:raise ValueError("INDEX_TOO_LARGE")
        return chunks.decode("utf-8","replace")

def _clean(value):
    return re.sub(r"\s+"," ",str(value or "")).strip()

def _rows(markup,city,url):
    soup=BeautifulSoup(markup,"html.parser")
    for node in soup(["script","style","nav","footer","header","form"]):
        node.decompose()
    candidates={}
    # Detect field IDs only inside a compact record, never by mining the
    # entire application page body (which mixes different developments).
    for element in soup.find_all(["h2","h3","h4","h5","li","article","tr"]):
        heading=_clean(element.get_text(" ",strip=True))[:600]
        if not 8<=len(heading)<=600 or NOISE.search(heading):continue
        match=ID_PATTERN.search(heading)
        if not match:continue
        desc=heading
        # A heading with exact file ID can inherit its immediately adjacent
        # paragraph, but not the entire page or another project's section.
        if len(desc)<120:
            other=element.find_next_sibling(["p","div"])
            if other:desc=_clean(desc+" "+other.get_text(" ",strip=True))[:600]
        if not COMMERCIAL.search(desc):continue
        if RESIDENTIAL.search(desc) and not re.search(
                r"\b(?:industrial|warehouse|factory|retail|commercial|"
                r"data.cent(?:er|re)|manufactur\w*|employment)\b",desc,re.I):
            continue
        ident=_clean(match.group(0)).upper()
        ident=re.sub(r"\s+"," ",ident)
        anchor=element.find("a",href=True)
        link=urljoin(url,anchor["href"]) if anchor else ""
        exact_link=link if _safe(link,url) else ""
        pid="EARLY_APP:"+city.upper().replace(" ","_")+":"+re.sub(r"\s+","",ident)
        entry={"project_id":pid,"city":city,"application_id":ident,
               "description":desc[:600],"source_url":url,
               "record_source_url":exact_link or url,
               "record_source_url_basis":("LINK_ON_APPLICATION_ENTRY_NOT_ID_VERIFIED"
                    if exact_link else "OFFICIAL_INDEX_CONTEXT_ONLY_NOT_EXACT_RECORD"),
               "source_record_date":"","source_record_date_basis":"NOT_PUBLISHED_IN_PARSED_ENTRY",
               "commercial_fit":"POTENTIAL_COMMERCIAL_NEEDS_REVIEW",
               "verification_required":"Confirm ID, application identity, source filing date, actual commercial scope and current phase"}
        prior=candidates.get(pid)
        if prior is None or len(desc)>len(prior["description"]):
            candidates[pid]=entry
    links={}
    for a in soup.find_all("a",href=True):
        name=_clean(a.get_text(" ",strip=True))[:190]
        if not LINK.search(name) or not name or NOISE.search(name):continue
        target=urljoin(url,a["href"])
        if not _safe(target,url) or target==url:continue
        links[target]={"city":city,"title":name,"url":target,"index_url":url,
                        "status":"LINK_ONLY_NOT_PARSED_AS_PROJECT",
                        "publication_date_verified":False}
        if len(links)>=100:break
    return list(candidates.values()),list(links.values())

def _write(path,rows,fields):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def run(results,*,today=None,fetcher=None,sources=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    source_list=sources or SOURCES
    path=root/STATE
    if path.exists():
        state=json.loads(path.read_text(encoding="utf-8"))
        if state.get("schema")!=1:raise ValueError("UNKNOWN_EARLY_APP_STATE")
    else:state={"schema":1,"projects":{},"links":{}}
    old=state["projects"];known_links=state["links"]
    baseline=not path.exists()
    records=[];changed=[];newlinks=[];source_audit=[]
    for city,url in source_list.items():
        status={"city":city,"source_url":url,"fetch_status":"UNKNOWN",
                "actual_application_rows":0,"new_or_changed":0,
                "links_observed":0,"verified_early_publication_dates":0,
                "full_document_extraction_verified":False}
        try:
            markup=(fetcher or _fetch)(url)
            entries,links=_rows(markup,city,url)
            status["fetch_status"]="INDEX_FETCHED"
            status["actual_application_rows"]=len(entries)
            status["links_observed"]=len(links)
            if not entries:status["fetch_status"]="INDEX_ONLY_NO_STRUCTURED_APPLICATIONS"
            for row in entries:
                pid=row["project_id"]
                digest=hashlib.sha256(_clean(row["description"]).casefold().encode()).hexdigest()
                prev=old.get(pid)
                observation=("INITIAL_BASELINE" if baseline and prev is None
                    else "FIRST_OBSERVED" if prev is None
                    else "RECORD_CHANGED" if prev.get("digest")!=digest else "UNCHANGED")
                first=prev.get("first_seen_local") if prev else day
                row.update(first_seen_local=first,observation=observation,
                           changed_fields=("description" if observation=="RECORD_CHANGED" else ""))
                records.append(row)
                if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):
                    changed.append(row);status["new_or_changed"]+=1
                old[pid]={"digest":digest,"first_seen_local":first,
                          "last_seen_local":day,"city":city}
            for item in links:
                url_key=item["url"]
                prev=known_links.get(url_key)
                obs="INITIAL_BASELINE" if baseline and prev is None else (
                    "FIRST_OBSERVED" if prev is None else "UNCHANGED")
                first=prev or day
                item.update(first_seen_local=first,observation=obs)
                if obs=="FIRST_OBSERVED":newlinks.append(item)
                known_links[url_key]=first
        except Exception as exc:
            status["fetch_status"]="FETCH_FAILED"
            status["error_type"]=type(exc).__name__
            status["reason"]=str(exc)[:180]
        source_audit.append(status)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    tmp.replace(path)
    _write(root/CANDIDATES,records,ROW_FIELDS)
    _write(root/NEW,changed,ROW_FIELDS)
    _write(root/LINKS,newlinks,LINK_FIELDS)
    summary={"cities_configured":len(source_list),
             "indexes_fetched":sum(x["fetch_status"]!="FETCH_FAILED" for x in source_audit),
             "indexes_failed":sum(x["fetch_status"]=="FETCH_FAILED" for x in source_audit),
             "cities_with_parsed_ids":sum(x["actual_application_rows"]>0 for x in source_audit),
             "application_candidate_rows":len(records),
             "new_or_changed_application_records":len(changed),
             "new_links":len(newlinks),
             "baseline_only":baseline,
             "project_filing_or_first_publication_dates_verified":0,
             "ai_calls":0,"automatically_promoted_to_canonical_projects":0,
             "city_status":source_audit,
             "all_candidates_csv":str(root/CANDIDATES),
             "new_or_changed_csv":str(root/NEW),
             "new_links_csv":str(root/LINKS),
             "warning":"Sources are official public indexes, not verified per-record pages. File numbers and commercial scope are review-only; no source-file date, contract, first publication, or new market lead is inferred."}
    (root/AUDIT).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
