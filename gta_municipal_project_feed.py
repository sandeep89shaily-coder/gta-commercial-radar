"""Read-only source-aware municipal project feed; public HTML only, zero paid AI.

Application IDs and address-only project listings are kept distinct. A newly
discovered record on first successful collection is baseline, never a new lead.
Individual source failures preserve source baselines and appear in diagnostics.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from gta_early_applications import _fetch, _clean, _safe

OAKVILLE="https://www.oakville.ca/business-development/planning-development/active-development-applications/"
SOURCES={
    "Halton Hills":[
        "https://www.haltonhills.ca/developmentproposalsunderreview"],
    "Cambridge":[
        "https://www.cambridge.ca/business-building-development/building-planning/current-development-applications/"],
    "Milton":[
        "https://www.milton.ca/business-development/planning-and-development/development-applications/development-application-notices/"],
    "Guelph":[
        "https://guelph.ca/city-government/planning-and-development/current-development-applications/"],
    "Oakville":[
        OAKVILLE+"ward-"+str(n)+"-development-and-site-plan-applications/"
        for n in range(1,8)],
}
# Distinct application identifiers use city-specific formats, not a synthetic
# ID inferred from arbitrary prose. A row with no ID remains a project signal.
ID_PATTERNS={
    "Halton Hills":re.compile(r"\bD(?:09|10|11|12|14|25)\s*(?:SPA|ZBA|OPA|SUB|PLC)?\s*\d{2}[.]\d{3}(?:[.]RV\d+)?\b",re.I),
    "Cambridge":re.compile(r"\b(?:OR|OP|R)\d{1,2}/\d{2}\b|\b30(?:CDM|T)-\d{5,6}\b",re.I),
    "Oakville":re.compile(r"\b(?:Z[.]|OPA\s*|SP\s*|24T-|24CDM-)\s*\d{2,6}(?:[.]\d{2,4})?(?:/\d{1,4})?\b|\b\d{4}[.]\d{3}/\d{2}\b",re.I),
    "Milton":re.compile(r"\b(?:Z|OPA|SP|D)-\d{2}/\d{2}\b",re.I),
}
SOURCE_TYPE="OFFICIAL_MUNICIPAL_HTML"
STATE="GTA_RADAR_MUNICIPAL_FEED_SEEN.json"
ALL="GTA_RADAR_MUNICIPAL_PROJECT_FEED.csv"
CHANGED="GTA_RADAR_MUNICIPAL_PROJECT_CHANGES.csv"
STATUS="GTA_RADAR_MUNICIPAL_PROJECT_FEED_STATUS.json"
COLUMNS=("project_id","city","application_id","project_title","address",
         "description","source_url","source_type","record_kind",
         "commercial_screen","first_seen_local","observation","verification_required")
COMMERCIAL=re.compile(r"\b(?:industrial|warehouse|commercial|retail|office|hotel|"
    r"restaurant|hospital|clinic|medical|manufactur\w*|distribution|storage|"
    r"factory|logistics|business|mixed.use|grocery|data.cent(?:er|re)|"
    r"employment|industrial)\b",re.I)
NOISE=re.compile(r"\b(?:privacy|accessibility|subscribe|cookie|web.?map|"
                 r"contact us|feedback|document library)\b",re.I)

def _id(city, text):
    pattern=ID_PATTERNS.get(city)
    match=pattern.search(text) if pattern else None
    return _clean(match.group(0)) if match else ""

def _project(city, title, description, source_url, *, application_id="", address=""):
    title=_clean(title)[:260]
    description=_clean(description)[:900]
    if len(title)<7 or NOISE.search(title):return None
    # A source URL or application number is mandatory; no fabricated IDs.
    if not _safe(source_url,SOURCES[city][0]):return None
    kind="APPLICATION_ID" if application_id else "PROJECT_INDEX_SIGNAL"
    identity=(application_id.upper() if application_id else source_url+"|"+title.casefold())
    key=hashlib.sha256((city+"|"+identity).encode()).hexdigest()[:20]
    return {"project_id":"MUNICIPAL:"+city.upper().replace(" ","_")+":"+key,
       "city":city,"application_id":application_id,"project_title":title,
       "address":address,"description":description,"source_url":source_url,
       "source_type":SOURCE_TYPE,"record_kind":kind,
       "commercial_screen":("POTENTIAL_COMMERCIAL_NEEDS_REVIEW"
           if COMMERCIAL.search(title+" "+description) else "UNCLASSIFIED_REVIEW"),
       "verification_required":("Verify project identity, current scope, dates,"
            " owner, construction status and procurement stage")}

def _halton(soup,url):
    out=[]
    for tr in soup.select("tr"):
        cells=tr.find_all(["td","th"],recursive=False)
        if len(cells)<4:continue
        location=_clean(cells[1].get_text(" ",strip=True))
        filetext=_clean(cells[2].get_text(" ",strip=True))
        desc=_clean(cells[3].get_text(" ",strip=True))
        # The source has D11SPA26.003, which the old generic pattern misses.
        ids=list(dict.fromkeys(m.group(0) for m in ID_PATTERNS["Halton Hills"].finditer(filetext)))
        if not ids:continue
        for ident in ids:
            row=_project("Halton Hills",location+" — "+ident,desc,url,
                         application_id=ident,address=location)
            if row:out.append(row)
    return out

def _cambridge(soup,url):
    # Application headings on this official page are followed by a section of
    # narrative. Stop at the next application heading to avoid cross-site data.
    chunks=[]
    heading=None
    out=[]
    for node in soup.find_all(["h2","h3","h4","h5","p"]):
        value=_clean(node.get_text(" ",strip=True))
        if not value:continue
        match=re.match(r"^\s*((?:OR|OP|R)\d{1,2}/\d{2}|30(?:CDM|T)-\d{5,6})\b",value,re.I)
        if match:
            if heading:
                row=_project("Cambridge",heading,
                    " ".join(chunks)[:900],url,application_id=_id("Cambridge",heading))
                if row:out.append(row)
            heading=value[:230]
            chunks=[]
        elif heading and len(chunks)<15:
            chunks.append(value[:350])
    if heading:
        row=_project("Cambridge",heading," ".join(chunks)[:900],url,
                     application_id=_id("Cambridge",heading))
        if row:out.append(row)
    return out

def _oakville(soup,url):
    out=[]
    for node in soup.find_all(["li","p","tr"]):
        txt=_clean(node.get_text(" ",strip=True))
        if len(txt)<15 or len(txt)>450:continue
        ident=_id("Oakville",txt)
        if not ident:continue
        a=node.find("a",href=True)
        link=urljoin(url,a["href"]) if a else url
        if not _safe(link,url):link=url
        row=_project("Oakville",txt[:220],txt,link,application_id=ident)
        if row:out.append(row)
    # Some ward pages use naked linked application titles, no list markup.
    for a in soup.find_all("a",href=True):
        txt=_clean(a.get_text(" ",strip=True))
        ident=_id("Oakville",txt)
        if ident and 15<=len(txt)<=260:
            link=urljoin(url,a["href"])
            if not _safe(link,url):link=url
            row=_project("Oakville",txt,txt,link,application_id=ident)
            if row:out.append(row)
    return out

def _milton(soup,url):
    out=[]
    for a in soup.find_all("a",href=True):
        title=_clean(a.get_text(" ",strip=True))
        if not re.search(r"(?i)(?:notice of complete application|statutory public meeting|"
                         r"application for temporary use|notice of application)",title):
            continue
        link=urljoin(url,a["href"])
        if not _safe(link,url) or link==url:continue
        ident=_id("Milton",title)
        row=_project("Milton",title,title,link,application_id=ident)
        if row:out.append(row)
    return out

def _guelph(soup,url):
    # The City's Current Development Projects table has addresses and types,
    # but typically NO application ID. Never mislabel these as filed IDs.
    out=[]
    for tr in soup.select("tr"):
        cells=tr.find_all(["td","th"],recursive=False)
        if len(cells)<2:continue
        addr=_clean(cells[0].get_text(" ",strip=True))
        kind=_clean(cells[1].get_text(" ",strip=True))
        if not re.search(r"(?i)\b(?:road|street|drive|avenue|boulevard|"
                         r"parkway|lane|court|crescent|highway|place)\b",addr):continue
        if not re.search(r"(?i)(?:plan|zone|subdivision|development|site)",kind):
            continue
        a=tr.find("a",href=True)
        link=urljoin(url,a["href"]) if a else url
        if not _safe(link,url):link=url
        row=_project("Guelph",addr,kind,link,address=addr)
        if row:out.append(row)
    return out

PARSERS={"Halton Hills":_halton,"Cambridge":_cambridge,
         "Oakville":_oakville,"Milton":_milton,"Guelph":_guelph}

def _parse(city,markup,url):
    soup=BeautifulSoup(markup,"html.parser")
    for tag in soup(["script","style","nav","footer","header"]):
        tag.decompose()
    return PARSERS[city](soup,url)

def run(results,*,today=None,fetcher=None,sources=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    state_path=root/STATE
    state=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"schema":1,"sources":{}}
    if state.get("schema")!=1:raise ValueError("UNRECOGNIZED_MUNICIPAL_FEED_STATE")
    all_rows=[];changed=[];audit=[]
    for city,urls in (sources or SOURCES).items():
        previous=state["sources"].get(city)
        seen=dict(previous.get("seen",{})) if previous else {}
        found={}
        failures=[]
        successful=0
        for url in urls:
            try:
                markup=(fetcher or _fetch)(url)
                items=_parse(city,markup,url)
                successful+=1
                for row in items:
                    key=row["project_id"]
                    if key not in found or len(row["description"])>len(found[key]["description"]):
                        found[key]=row
            except Exception as exc:
                failures.append({"url":url,"error":type(exc).__name__+":"+str(exc)[:140]})
        # Incomplete multi-page feeds must not declare a complete baseline.
        complete=successful==len(urls)
        new=0
        for key,row in sorted(found.items()):
            digest=hashlib.sha256((row["project_title"]+"|"+row["description"]+"|"+
                                    row["application_id"]).encode()).hexdigest()
            prior=seen.get(key)
            observation=("INITIAL_BASELINE" if previous is None or not previous.get("complete")
                         else "FIRST_OBSERVED" if prior is None
                         else "RECORD_CHANGED" if prior["digest"]!=digest
                         else "UNCHANGED")
            row["first_seen_local"]=prior.get("first_seen_local",day) if prior else day
            row["observation"]=observation
            all_rows.append(row)
            if observation in ("FIRST_OBSERVED","RECORD_CHANGED") and complete:
                changed.append(row);new+=1
            if complete:
                seen[key]={"digest":digest,"first_seen_local":row["first_seen_local"]}
        if complete:
            state["sources"][city]={"seen":seen,"complete":True,"baseline_date":
                                   previous.get("baseline_date",day) if previous else day}
        audit.append({"city":city,"configured_pages":len(urls),
            "pages_fetched":successful,"complete":complete,
            "application_id_rows":sum(bool(r["application_id"]) for r in found.values()),
            "project_only_signals":sum(not r["application_id"] for r in found.values()),
            "new_or_changed":new,"failures":failures[:20],
            "state":"COLLECTED" if complete and found else
                "NO_MATCHING_PROJECT_RECORDS" if complete else "INCOMPLETE_SOURCE"})
    for filename,rows in ((ALL,all_rows),(CHANGED,changed)):
        with (root/filename).open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=COLUMNS)
            writer.writeheader();writer.writerows(rows)
    temp=state_path.with_suffix(".tmp")
    temp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    temp.replace(state_path)
    summary={"source_status":audit,
             "application_id_rows":sum(bool(r["application_id"]) for r in all_rows),
             "project_only_signals":sum(not r["application_id"] for r in all_rows),
             "new_or_changed":len(changed),"paid_ai_calls":0,
             "warning":"Project-only signals are not verified applications. No first publication date inferred; incomplete sources do not advance first-seen baselines."}
    (root/STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
