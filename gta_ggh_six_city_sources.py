"""Six additional GGH municipal planning sources with strict application evidence.

Official index source configuration is NOT a working application collector.
Only labelled municipal file numbers produce application candidates. Optional
bounded notice-page inspection uses an injected fetcher, or the parent GGH
collector's same-host/robots/DNS/no-redirect checked HTML fetch.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

SOURCES = {
 "Richmond Hill":"https://www.richmondhill.ca/en/learn-more/Planning-Development.aspx",
 "Newmarket":"https://www.newmarket.ca/business-development/development-planning/development-applications/current-applications",
 "Innisfil":"https://www.innisfil.ca/building-development/planning-development/proposed-developments",
 "New Tecumseth":"https://www.newtecumseth.ca/build-here/development/proposed-developments/",
 "Bradford West Gwillimbury":"https://www.townofbwg.com/news/statutoryplanning-notices/",
 "Thorold":"https://www.thorold.ca/building-business-development/planning-and-development/development-applications/",
}
SCOUT_CITIES = frozenset(("New Tecumseth","Bradford West Gwillimbury"))
MAX_NOTICE_LINKS = 6
FILE = re.compile(r"(?<![A-Z0-9])(?:D(?:10|11|12|13|14|15|16)[-/]\d{2,4}[-/]\d{1,4}"
                  r"|(?:OPA|ZBA|SPC|SPA|SP|SUB)\s*[-#]?\s*\d{2,4}[-/]\d{1,5}"
                  r"|(?:OP|Z)\.\d{2}\.\d{3})(?![A-Z0-9])",re.I)
LABEL = re.compile(r"\b(?:City\s+)?File\s+(?:No\.?|Number)\s*:?\s*",re.I)
NOISE = re.compile(r"\b(?:application form|how to apply|committee member|"
    r"privacy policy|newsletter|accessibility|download application form)\b",re.I)
NOTICE = re.compile(r"(?:notice.of.(?:complete.application|public.meeting|public.hearing)"
    r"|planning.act.notice|notice.of.intention|proposed.development)",re.I)
SOURCE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean(s):return re.sub(r"\s+"," ",str(s or "")).strip()


def _safe(url,index):
    try:
        p,o=urlparse(url),urlparse(index)
        return (p.scheme=="https" and p.hostname==o.hostname and
                p.port in (None,443) and not p.username and not p.password
                and not p.fragment and not p.query)
    except ValueError:
        return False


def notice_links(html,city,index):
    if city not in SCOUT_CITIES:return []
    soup=BeautifulSoup(html,"html.parser")
    main=soup.find("main") or soup
    chosen=[];seen=set()
    for anchor in main.find_all("a",href=True):
        title=_clean(anchor.get_text(" ",strip=True))
        candidate=urljoin(index,str(anchor.get("href","")).strip())
        path=urlparse(candidate).path.lower()
        if (not _safe(candidate,index) or candidate==index or candidate in seen or
            path.endswith((".pdf",".doc",".docx",".csv",".zip"))):
            continue
        if not NOTICE.search(title+" "+path.replace("-",".")):
            continue
        if NOISE.search(title):continue
        # A notice-page link is a candidate for inspection, not an application.
        seen.add(candidate);chosen.append(candidate)
        if len(chosen)>=MAX_NOTICE_LINKS:break
    return chosen


def _id_chunks(soup):
    """Only explicit file labels or notice-specific supporting-document ID links."""
    main=soup.find("main") or soup.find("article") or soup
    for element in main.select("script,style,nav,footer,form"):
        element.decompose()
    text=_clean(main.get_text(" ",strip=True))
    ids=[]
    # The next 160 characters belong to the labelled field; do not search
    # arbitrary page-wide numeric strings or old application references.
    for match in LABEL.finditer(text):
        bounded=text[match.end():match.end()+145]
        for entry in FILE.finditer(bounded):
            ident=entry.group().upper().replace(" ","")
            if ident not in ids:ids.append(ident)
    return text,ids


def extract_notice(city,html,index,record_url,record_factory):
    """Collect only municipally labelled application file IDs from one page."""
    if not _safe(record_url,index):
        raise ValueError("UNTRUSTED_OFFICIAL_NOTICE_HOST")
    soup=BeautifulSoup(html,"html.parser")
    text,identifiers=_id_chunks(soup)
    if not identifiers:
        return []
    title=soup.find("h1")
    heading=_clean(title.get_text(" ",strip=True)) if title else ""
    if NOISE.search(heading):heading=""
    info=(heading+" — "+text[:600])[:790]
    address=""
    addr_match=re.search(r"\b(?:Location|Subject Lands?|Municipal Address)\s*:\s*(.{5,115}?)(?=\s+(?:File|Agent|Owner|Purpose|Proposal|Meeting|Notice)\b|$)",text,re.I)
    if addr_match:address=_clean(addr_match.group(1))[:200]
    owner_match=re.search(r"\b(?:Owner|Applicant)\s*:\s*([A-Za-z][\w\s&.,'()-]{2,110}?)(?=\s+(?:Agent|File|Location|Address|Proposal|Purpose)\s*:|$)",text,re.I)
    applicant=_clean(owner_match.group(1))[:160] if owner_match else ""
    # Do not infer a publication date from a meeting date or crawl timestamp.
    date=""
    node=soup.find("time",attrs={"datetime":True})
    if node:
        token=str(node.get("datetime",""))[:10]
        if SOURCE_DATE.fullmatch(token):
            import datetime
            try:datetime.date.fromisoformat(token);date=token
            except ValueError:pass
    result=[]
    for number in identifiers[:12]:
        row=record_factory(city,number,address,info,index,
            record_url=record_url,applicant=applicant,kind="OFFICIAL_PLANNING_NOTICE",
            date=date,date_basis="OFFICIAL_NOTICE_DISPLAY_DATE_NOT_FIRST_PUBLICATION")
        if row:result.append(row)
    return result


def extract_thorold(html,index,record_factory):
    """Thorold publishes sections with explicit City File No. and documents.

    Do not infer an application ID from historical rezoning references in the
    proposal or from the filename of an unrelated supporting study.
    """
    soup=BeautifulSoup(html,"html.parser")
    main=soup.find("main") or soup
    found={}
    headers=main.find_all(["h2","h3","h4"])
    for head in headers:
        title=_clean(head.get_text(" ",strip=True))
        if len(title)<10 or len(title)>250 or NOISE.search(title):continue
        sections=[]
        for sibling in head.next_siblings:
            if getattr(sibling,"name",None) in ("h2","h3","h4"):break
            text=_clean(sibling.get_text(" ",strip=True) if hasattr(sibling,"get_text") else sibling)
            if text:sections.append(text[:900])
            if sum(len(v) for v in sections)>1900:break
        bounded=_clean(" ".join(sections))
        if len(bounded)<20:continue
        # Capture the labelled section only, not all file numbers elsewhere.
        ids=[]
        for m in LABEL.finditer(bounded):
            for pattern in FILE.finditer(bounded[m.end():m.end()+130]):
                value=pattern.group().upper().replace(" ","")
                if value not in ids:ids.append(value)
        if not ids:continue
        for ident in ids[:5]:
            row=record_factory("Thorold",ident,title,(title+" — "+bounded)[:800],
                               index,record_url=index,kind="OFFICIAL_ACTIVE_APPLICATION")
            if row:found[row["project_id"]]=row
    return list(found.values())
