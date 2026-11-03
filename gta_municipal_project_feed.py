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
    "Hamilton":[
        "https://www.hamilton.ca/city-council/news-notices/news-releases?category=143"],
    "Brampton":[
        "https://letsconnect.brampton.ca/yourcityplans"],
    "Burlington":[
        "https://www.burlington.ca/Modules/News/en/Development"],
    "Vaughan":[
        "https://www.vaughan.ca/about-city-vaughan/departments/office-city-clerk/public-notices"],
    "Kitchener":[
        "https://www.kitchener.ca/strategic-plans-and-projects/projects/"],
}
# Distinct application identifiers use city-specific formats, not a synthetic
# ID inferred from arbitrary prose. A row with no ID remains a project signal.
ID_PATTERNS={
    "Halton Hills":re.compile(r"\bD(?:09|10|11|12|14|25)\s*(?:SPA|ZBA|OPA|SUB|PLC)?\s*\d{2}[.]\d{3}(?:[.]RV\d+)?\b",re.I),
    "Cambridge":re.compile(r"\b(?:OR|OP|R)\d{1,2}/\d{2}\b|\b30(?:CDM|T)-\d{5,6}\b",re.I),
    "Oakville":re.compile(r"\b(?:Z[.]|OPA\s*|SP\s*|24T-|24CDM-)\s*\d{2,6}(?:[.]\d{2,4})?(?:/\d{1,4})?\b|\b\d{4}[.]\d{3}/\d{2}\b",re.I),
    "Milton":re.compile(r"\b(?:Z|OPA|SP|D)-\d{2}/\d{2}\b",re.I),
    "Hamilton":re.compile(r"\bDPA-20\d{2}-\d{4,6}\b",re.I),
    "Brampton":re.compile(r"\b(?:OZS|SP|PDC)-20\d{2}-\d{4}\b",re.I),
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
    # Town's active-application table is dynamically rendered and absent
    # from the original HTML response. Preserve actual official major project
    # links as *project signals*, never fabricated application numbers.
    if not out:
        seen=set()
        for a in soup.find_all("a",href=True):
            href=urljoin(url,a["href"])
            if (href in seen or not _safe(href,url) or
                    "/work/planning-development/active-development-applications/" not in href):
                continue
            title=_clean(a.get_text(" ",strip=True))
            if len(title)<8:continue
            row=_project("Halton Hills",title,title,href)
            if row:out.append(row);seen.add(href)
            if len(out)>=25:break
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


def _notice_links(markup,url):
    """Source-specific Hamilton complete-application notices only."""
    soup=BeautifulSoup(markup,"html.parser")
    selected=[];seen=set()
    for a in soup.find_all("a",href=True):
        title=_clean(a.get_text(" ",strip=True))
        link=urljoin(url,a["href"])
        if (link in seen or not _safe(link,url)
                or "complete application" not in title.lower()
                or "/news-releases/" not in urlparse(link).path):
            continue
        selected.append(link);seen.add(link)
        if len(selected)>=16:break
    return selected

def _hamilton(soup,url):
    # Detail-page source: stable official DPA number plus the municipal
    # proposal/address text. Index pages intentionally yield no fake IDs.
    text=_clean(soup.get_text(" ",strip=True))
    match=re.search(r"\bFile Number\s*:\s*(DPA-20\d{2}-\d{4,6})\b",text,re.I)
    if not match:return []
    ident=match.group(1)
    heading=soup.find("h1")
    title=_clean(heading.get_text(" ",strip=True)) if heading else "Hamilton "+ident
    proposal=re.search(r"\bProposal\s*:\s*(.{10,850}?)(?=\s+\bAddress\s*:|\s+\bFile Number\s*:)",text,re.I)
    desc=proposal.group(1) if proposal else title
    address=re.search(r"\bAddress\s*:\s*(.{5,220}?)(?=\s+\bFile Number\s*:)",text,re.I)
    addr=address.group(1) if address else ""
    row=_project("Hamilton",title,desc,url,application_id=ident,address=addr)
    return [row] if row else []

def _brampton(soup,url):
    # The City's public PDC community page includes featured applications
    # with their OZS numbers. No search form or inaccessible GIS is used.
    out=[]
    for node in soup.find_all(["h2","h3","h4","p","li"]):
        txt=_clean(node.get_text(" ",strip=True))
        if len(txt)>1200:continue
        ids=list(dict.fromkeys(m.group(0) for m in ID_PATTERNS["Brampton"].finditer(txt)))
        if not ids:continue
        container=node.parent
        context=_clean(container.get_text(" ",strip=True))[:900] if container else txt
        for ident in ids:
            row=_project("Brampton",txt[:210],context,url,application_id=ident)
            if row:out.append(row)
    return out

def _burlington(soup,url):
    # The news/project directory can expose named ward development pages
    # even when it does not expose a file number. Keep as project signals.
    out=[]
    for a in soup.find_all("a",href=True):
        title=_clean(a.get_text(" ",strip=True))
        link=urljoin(url,a["href"])
        if not _safe(link,url) or link==url:continue
        if re.search(r"\.(?:png|jpe?g|pdf|webp|docx?)$",urlparse(link).path,re.I):
            continue
        if (len(title)<14 or
                not re.search(r"(?i)(?:development|project|ward\s*[1-6]|"
                              r"\d{2,5}\s+[A-Za-z].{1,60}(?:street|road|drive|"
                              r"avenue|boulevard|lane))",title)):
            continue
        row=_project("Burlington",title,title,link)
        if row:out.append(row)
    return out


def _vaughan(soup,url):
    """Source-specific statutory notice extraction, excluding minor variances.

    The public registry exposes file numbers, subject lands, meeting dates and
    proposed uses in ordinary HTML. A notice is not proof of a new filing.
    """
    text=_clean(soup.get_text(" ",strip=True))
    records=[]
    pattern=re.compile(r"\b(?:OP|Z|DA)\.\d{2}\.\d{3}\b",re.I)
    for section in re.split(r"\bCity File No\.\s*:",text,flags=re.I)[1:]:
        head=section.split("Subject Land:",1)[0]
        ids=list(dict.fromkeys(x.group(0) for x in pattern.finditer(head)))
        if not ids:continue
        land=re.search(r"Subject Land:\s*(.{4,260}?)\s*Meeting Date:",section,re.I)
        desc=re.search(r"Notice Description:\s*(.{10,1000}?)(?=\s*(?:Notice Type:|Notice of Public Meeting|City File No\.:|$))",section,re.I)
        description=_clean(desc.group(1)) if desc else ""
        if not description or not COMMERCIAL.search(description):
            continue
        if re.search(r"(?i)\b(?:cabana|hot tub|backyard deck|existing shed)\b",description):
            continue
        address=_clean(land.group(1)) if land else ""
        for ident in ids:
            row=_project("Vaughan",ident+" — "+address,description,url,
                         application_id=ident,address=address)
            if row:records.append(row)
    return records


def _kitchener(soup,url):
    """Official City project index: project-only signals, not applications."""
    result=[]
    seen=set()
    for a in soup.find_all("a",href=True):
        target=urljoin(url,a["href"])
        path=urlparse(target).path.lower()
        if not _safe(target,url) or target==url or target in seen:
            continue
        if "/strategic-plans-and-projects/projects/" not in path:
            continue
        title=_clean(a.get_text(" ",strip=True))
        if len(title)<14 or len(title)>180:
            continue
        if title.casefold() in ("projects","view all projects","strategic plans and projects"):
            continue
        row=_project("Kitchener",title,title,target)
        if row:
            result.append(row)
            seen.add(target)
        if len(result)>=60:break
    return result


# Some municipal indexes show an address only, while the linked official
# application page contains the actual file identifier. Never derive IDs from
# the address or count a linked page as an application until verified in HTML.
GUELPH_FILE=re.compile(r"\b(?:OZS|SP|SUB|OP|ZBA)\s*[-.]?\s*(?:20)?\d{2}[-.]\d{2,5}\b",re.I)
HALTON_DETAIL_FILE=re.compile(r"\bD(?:09|10|11|12|14|25)(?:OPA|SPA|ZBA|SUB|PLC)?\d{2}[.]\d{2,4}(?:[.]RV\d+)?\b",re.I)

def _detail_project(city,markup,url):
    soup=BeautifulSoup(markup,"html.parser")
    for node in soup(["script","style","nav","footer","header"]):
        node.decompose()
    heading=soup.find("h1")
    title=_clean(heading.get_text(" ",strip=True)) if heading else ""
    text=_clean(soup.get_text(" ",strip=True))
    if not title or not text:return []
    if city=="Guelph":
        # The City's project pages explicitly label a File Number.
        ident_match=re.search(r"\bFile\s+Number\s*:?\s*"+
            GUELPH_FILE.pattern,text,re.I)
        if ident_match:
            ids=list(dict.fromkeys(x.group(0) for x in GUELPH_FILE.finditer(ident_match.group(0))))
        else:
            ids=[]
    elif city=="Halton Hills":
        # Town project pages sometimes print multiple associated file numbers.
        # Accept only printed identifiers in the official page body.
        ids=list(dict.fromkeys(x.group(0) for x in HALTON_DETAIL_FILE.finditer(text)))
    else:return []
    # Exclude nav / unrelated sidebar prose by taking bounded first-paragraph
    # context; the official source URL remains linked for verification.
    description=""
    for p in soup.find_all("p"):
        value=_clean(p.get_text(" ",strip=True))
        if len(value)>=35 and not NOISE.search(value):
            description=value[:800];break
    if not description:description=title
    out=[]
    for ident in ids[:5]:
        row=_project(city,title,description,url,application_id=ident,address=title)
        if row:out.append(row)
    return out

def _detail_targets(city,items,index_url,limit=20):
    if city not in ("Guelph","Halton Hills"):return []
    targets=[]
    for row in items:
        url=row.get("source_url","")
        if (url and url!=index_url and _safe(url,index_url) and
                urlparse(url).query=="" and url not in targets):
            targets.append(url)
            if len(targets)>=limit:break
    return targets

PARSERS={"Halton Hills":_halton,"Cambridge":_cambridge,
         "Oakville":_oakville,"Milton":_milton,"Guelph":_guelph,
         "Hamilton":_hamilton,"Brampton":_brampton,"Burlington":_burlington,
         "Vaughan":_vaughan,"Kitchener":_kitchener}

def _parse(city,markup,url):
    soup=BeautifulSoup(markup,"html.parser")
    for tag in soup(["script","style","nav","footer","header"]):
        tag.decompose()
    return PARSERS[city](soup,url)

def run(results,*,today=None,fetcher=None,sources=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    path=root/STATE
    state=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema":1,"sources":{}}
    if state.get("schema")!=1:raise ValueError("UNRECOGNIZED_MUNICIPAL_FEED_STATE")
    all_rows={};changed={};audits=[]
    for city,urls in (sources or SOURCES).items():
        city_state=state["sources"].get(city,{})
        old_pages=city_state.get("pages",{})
        updated_pages=dict(old_pages)
        found={}
        errors=[]
        pages_fetched=0
        city_new=set()
        page_status=[]
        for url in urls:
            # A ward/list page is an independent baseline. A failed page cannot
            # roll back or suppress good pages in the same municipality.
            old_page=old_pages.get(url)
            if old_page is None and "seen" in city_state:
                # Backward-compatible migration from city-level v1 ledger.
                old_page={"seen":city_state["seen"],
                          "baseline_date":city_state.get("baseline_date",day)}
            try:
                markup=(fetcher or _fetch)(url)
                items=_parse(city,markup,url)
                if city=="Hamilton":
                    for link in _notice_links(markup,url):
                        detail=(fetcher or _fetch)(link)
                        items.extend(_parse(city,detail,link))
                if city in ("Guelph","Halton Hills"):
                    # Official project detail pages are independent evidence;
                    # an unavailable detail is recorded without suppressing
                    # successfully extracted index signals.
                    for link in _detail_targets(city,items,url):
                        try:
                            detail=(fetcher or _fetch)(link)
                            extracted=_detail_project(city,detail,link)
                            if extracted:
                                # Avoid double-counting the address-only signal
                                # when the same page establishes a real file.
                                items=[v for v in items if not (
                                    v.get("source_url")==link and
                                    not v.get("application_id"))]
                                items.extend(extracted)
                        except Exception as exc:
                            errors.append({"url":link,"error":type(exc).__name__+
                                           ":"+str(exc)[:140],
                                           "stage":"DETAIL_PROJECT"})
                unique={}
                for row in items:
                    key=row["project_id"]
                    if key not in unique or len(row["description"])>len(unique[key]["description"]):
                        unique[key]=row
                before=old_page.get("seen",{}) if old_page else {}
                after=dict(before)
                for key,row in unique.items():
                    digest=hashlib.sha256((row["project_title"]+"|"+row["description"]+
                                           "|"+row["application_id"]).encode()).hexdigest()
                    prior=before.get(key)
                    obs=("INITIAL_BASELINE" if old_page is None and prior is None
                         else "FIRST_OBSERVED" if prior is None
                         else "RECORD_CHANGED" if prior["digest"]!=digest
                         else "UNCHANGED")
                    row["first_seen_local"]=prior.get("first_seen_local",day) if prior else day
                    row["observation"]=obs
                    existing=found.get(key)
                    if existing is None or len(row["description"])>len(existing["description"]):
                        found[key]=row
                    if obs in ("FIRST_OBSERVED","RECORD_CHANGED"):
                        changed[key]=row
                        city_new.add(key)
                    after[key]={"digest":digest,"first_seen_local":row["first_seen_local"]}
                # Empty/unparsed first fetch cannot establish an
                # application baseline; otherwise parser changes look like new leads.
                if unique or old_page is not None:
                    updated_pages[url]={"seen":after,"baseline_date":
                                        old_page.get("baseline_date",day) if old_page else day}
                pages_fetched+=1
                page_status.append({"url":url,"status":"COLLECTED",
                                    "application_ids":sum(bool(v["application_id"]) for v in unique.values()),
                                    "project_only_signals":sum(not v["application_id"] for v in unique.values())})
            except Exception as exc:
                failure={"url":url,"error":type(exc).__name__+":"+str(exc)[:150]}
                errors.append(failure)
                page_status.append({"url":url,"status":"FAILED",
                                    "error":failure["error"]})
        if updated_pages:
            state["sources"][city]={"pages":updated_pages}
        for key,row in found.items():
            existing=all_rows.get(key)
            if existing is None or len(row["description"])>len(existing["description"]):
                all_rows[key]=row
        audits.append({"city":city,"configured_pages":len(urls),
             "pages_fetched":pages_fetched,"complete":pages_fetched==len(urls),
             "application_id_rows":sum(bool(r["application_id"]) for r in found.values()),
             "project_only_signals":sum(not r["application_id"] for r in found.values()),
             "new_or_changed":len(city_new),"failures":errors[:20],
             "page_status":page_status,
             "state":"COLLECTED" if pages_fetched==len(urls) and found else
                 "NO_MATCHING_PROJECT_RECORDS" if pages_fetched==len(urls) else
                 "PARTIAL_SOURCE_FAILURE" if pages_fetched else "INCOMPLETE_SOURCE"})
    for filename,rows in ((ALL,list(all_rows.values())),(CHANGED,list(changed.values()))):
        with (root/filename).open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=COLUMNS)
            writer.writeheader();writer.writerows(rows)
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    temp.replace(path)
    summary={"source_status":audits,
             "application_id_rows":sum(bool(r["application_id"]) for r in all_rows.values()),
             "project_only_signals":sum(not r["application_id"] for r in all_rows.values()),
             "new_or_changed":len(changed),"paid_ai_calls":0,
             "warning":"Project-only signals are not verified applications; every city page has an independent baseline. No first-publication date inferred."}
    (root/STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
