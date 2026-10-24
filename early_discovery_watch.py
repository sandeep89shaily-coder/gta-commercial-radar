"""Early public municipal project discovery — manual, free, review only.

Burlington: discover project detail URLs from City's six current-development wards.
Brampton: discover Planning & Development Committee meeting agendas from published
eSCRIBE calendar; extract numbered planning items and retain actual meeting dates.

No bypass of access restrictions, no private contacts, no V8/DeepSeek/scheduler.
Incomplete, blocked or unparsable sources fail closed, preserving SQLite history.
"""
from __future__ import annotations
import argparse
import csv
import re
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from bs4 import BeautifulSoup
import requests
from early_cue_watch import db_setup, save_source, _write_csv, parse_burlington

BURLINGTON_HOME="https://www.burlington.ca/en/planning-and-development/planning-and-development.aspx"
BRAMPTON_CALENDAR="https://pub-brampton.escribemeetings.com/MeetingsCalendarView.aspx"
SOURCES=("burlington_ward_discovery","brampton_planning_agendas")
ALLOWED={"www.burlington.ca","burlington.ca","pub-brampton.escribemeetings.com"}
FIELDS=("source_id","record_id","title","site","company","company_role","stage",
        "signal_type","source_date","date_basis","source_url","commercial_fit",
        "procurement_status","verification","first_seen_at","last_seen_at",
        "current_snapshot_status","description","not_sale_ready_reason")
STATUS=("source_id","status","fetched","new","updated","baseline","coverage",
        "discovered_pages","fetched_pages","warning","error")
CHANGES=("observed_at","source_id","record_id","change_type","title","site",
         "source_date","source_url","commercial_fit")
BURLINGTON_BLOCKED=("source_url","problem","impact")
TITLE_SCOPE=re.compile(r"\b(?:industrial|commercial|employment|warehouse|"
    r"manufactur\w*|data cent(?:er|re)|retail|hotel|office|medical|"
    r"cold storage|energy|logistic\w*|distribution|waste processing)\b",re.I)
RESIDENTIAL=re.compile(r"\b(?:residential|apartments?|townhouses?|dwellings?|homes)\b",re.I)
FILE=re.compile(r"\b(?:OZS|SPA|PRE|OZ|C\d{2}|520|505|535)-[0-9A-Za-z/-]{3,}\b",re.I)
DATE=re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
                r"([A-Z][a-z]+)\s+(\d{1,2}),?\s+(20\d{2})",re.I)


def _text(node):
    return " ".join(node.stripped_strings).strip() if node else ""


def _link(base,href):
    url=urljoin(base,href)
    p=urlparse(url)
    if p.scheme!="https" or p.hostname not in ALLOWED:
        raise ValueError("Untrusted/non-HTTPS source URL")
    return url.split("#",1)[0]


def fetch(session,url):
    _link(url,url)
    response=session.get(url,timeout=(10,45),headers={
        "User-Agent":"GTA-Radar-Public-EarlyResearch/0.3 (manual review)"})
    response.raise_for_status()
    html=response.text
    if len(html)<220 or "<html" not in html[:3000].lower():
        raise RuntimeError("Official page blocked, empty or not HTML")
    return html


def classify(raw):
    positive=bool(TITLE_SCOPE.search(raw))
    residential=bool(RESIDENTIAL.search(raw))
    if positive and residential:return "MIXED_USE_REVIEW"
    if positive:return "POSSIBLE_COMMERCIAL"
    if residential:return "RESIDENTIAL_LIKELY"
    return "USE_UNKNOWN"


def discover_burlington_ward_urls(html,origin=BURLINGTON_HOME):
    """Only follow exact municipal ward links in Current Development Projects nav."""
    soup=BeautifulSoup(html,"html.parser")
    wards={}
    for a in soup.find_all("a",href=True):
        name=_text(a)
        if not re.fullmatch(r"Ward\s*[1-6]",name,re.I):continue
        context=" ".join(_text(x)[:240] for x in
                         (a.parent,a.parent.parent if a.parent else None))
        href=a["href"]
        if "development" not in (context+" "+href).lower():continue
        try:url=_link(origin,href)
        except ValueError:continue
        if urlparse(url).hostname not in ("www.burlington.ca","burlington.ca"):continue
        wards[int(re.search(r"[1-6]",name).group())]=url
    if len(wards)<3:
        raise RuntimeError("City Burlington ward development index not exposed; cannot infer coverage")
    return [wards[k] for k in sorted(wards)]


def discover_burlington_project_urls(html,origin):
    """Strict known URL prefix: never wander the entire municipal site."""
    soup=BeautifulSoup(html,"html.parser")
    pages={}
    for a in soup.find_all("a",href=True):
        try:url=_link(origin,a["href"])
        except ValueError:continue
        path=urlparse(url).path.lower()
        if not path.startswith("/en/news/current-development-projects/"):
            continue
        if not path.endswith(".aspx"):continue
        if len(url)>320:continue
        pages[url]=_text(a)[:200]
    if not pages:raise RuntimeError("Ward has no linked official project pages")
    return pages


def burlington_records(session,max_pages=120):
    home=fetch(session,BURLINGTON_HOME)
    ward_urls=discover_burlington_ward_urls(home)
    if len(ward_urls)>6:raise RuntimeError("Unreasonable ward index")
    discovered={}
    failures=[]
    for ward in ward_urls:
        html=fetch(session,ward)
        discovered.update(discover_burlington_project_urls(html,ward))
    if len(discovered)>max_pages:
        raise RuntimeError("More Burlington projects than bounded scope; refuse partial snapshot")
    records=[]
    for url in sorted(discovered):
        try:
            item=parse_burlington(fetch(session,url),url)
            item["source_id"]="burlington_ward_discovery"
            item["date_basis"]="PUBLIC_PAGE_MENTIONS_EVENT_NOT_PUBLISH_DATE"
            item["description"]=item.get("attributes",{}).get("proposal","")
            item["commercial_fit"]=classify(item["title"]+" "+item["description"])
            item["procurement_status"]="UNKNOWN"
            records.append(item)
        except (ValueError,RuntimeError,requests.RequestException) as err:
            failures.append((url,type(err).__name__))
    if not records:
        raise RuntimeError("No accessible Burlington project detail records")
    # A 403 is a real publisher restriction, not an empty municipality.
    # Keep partial retrieved items for a review CSV, but DO NOT commit a
    # partial snapshot that could later create misleading NEW alerts.
    return records,{"discovered":len(discovered),"fetched":len(records),
                   "wards":len(ward_urls),"blocked_details":failures}


def meeting_id(url):
    query=parse_qs(urlparse(url).query)
    for key in ("Id","ID","MeetingId","meetingId"):
        value=query.get(key,[])
        if value and re.fullmatch(r"[0-9a-f-]{36}",value[0],re.I):
            return value[0].lower()
    return ""


def parse_calendar(html,origin=BRAMPTON_CALENDAR):
    """Extract links associated with PDC only; calendar is not a full PDF archive."""
    soup=BeautifulSoup(html,"html.parser")
    result={}
    for a in soup.find_all("a",href=True):
        # A calendar often has many committees in the same BODY. Never walk
        # up to body and mistakenly treat all meeting links as planning.
        context=a
        matched=False
        for depth in range(4):
            if context is None or context.name in ("html","body"):break
            block=_text(context)
            if "Planning and Development Committee" in block and len(block)<900:
                matched=True
                break
            context=context.parent
        if not matched:continue
        try:url=_link(origin,a["href"])
        except ValueError:continue
        key=meeting_id(url)
        if not key:continue
        if urlparse(url).hostname!="pub-brampton.escribemeetings.com":continue
        # Honor only published meeting URLs, never guessed meeting IDs.
        result[key]="https://pub-brampton.escribemeetings.com/Meeting.aspx?"+urlencode(
             {"Agenda":"Agenda","Id":key,"lang":"English"})
    if not result:
        raise RuntimeError("No publicly linked Brampton planning meetings; calendar may require JS")
    return result


def parse_meeting_agenda(html,url):
    soup=BeautifulSoup(html,"html.parser")
    page=_text(soup)
    if "Planning" not in page or "Committee" not in page or "Agenda" not in page[:3000]:
        raise RuntimeError("Unexpected agenda page or access challenge")
    m=DATE.search(page[:1500])
    if not m:
        raise RuntimeError("Meeting date not identifiable from official agenda")
    # Meeting date is NOT web publication date.
    meeting=datetime.strptime(" ".join(m.groups()),"%B %d %Y").date().isoformat()
    # Planning sections are numbered application headings often h3/h4, and may
    # contain file labels in ordinary text. Restrict to file-number blocks.
    text=soup.get_text("\n",strip=True)
    entries=[]
    pattern=re.compile(r"(?im)^\s*(?:File:\s*)?(OZS-\d{4}-\d{3,5}|SPA-\d{4}-\d{3,5}|PRE-\d{4}-\d{3,5})"
                      r"\b[^\n]{0,100}")
    for match in pattern.finditer(text):
        window=text[match.start():match.start()+1000]
        next_id=pattern.search(window,10)
        if next_id:window=window[:next_id.start()]
        key=match.group(1).upper()
        context=" ".join(window.splitlines())[:950]
        # Avoid repeat staff report and attachment headings for same file.
        if any(x["record_id"].endswith("|"+key) for x in entries):continue
        location=re.search(r"\bLocation\s*:\s*(.{7,130}?)(?:\bWard\s*\d+|\bRecommendation\b|$)",context,re.I)
        party=re.search(r"\bApplicant/Consultant\s*:\s*(.{4,180}?)(?:\bPurpose\s*:|\bLocation\s*:|$)",context,re.I)
        scope=re.search(r"\bPurpose\s*:\s*(.{8,450}?)(?:\bLocation\s*:|$)",context,re.I)
        description=(scope.group(1).strip() if scope else context[0:350])
        entries.append(dict(
            source_id="brampton_planning_agendas",record_id=meeting_id(url)+"|"+key,
            title="Brampton Planning "+key,site=location.group(1).strip() if location else "",
            company=party.group(1).strip() if party else "",
            company_role="APPLICANT_AND_CONSULTANT_UNSEPARATED_NOT_BUYER",
            stage="PLANNING_COMMITTEE_AGENDA",signal_type="PUBLIC_AGENDA_FILE",
            source_date="",date_basis="MEETING_DATE_NOT_PUBLICATION_DATE",
            meeting_date=meeting,source_url=url,description=description,
            commercial_fit=classify(description),procurement_status="UNKNOWN",
            verification="PUBLIC_AGENDA_NOT_UNAWARDED_WORK",
            attributes={"meeting_date":meeting,"file_number":key}))
    if not entries:
        raise RuntimeError("No parsable OZS/SPA/PRE agenda application IDs; do not treat as zero")
    return entries


def _brampton_calendar_dates(html):
    """Published meeting scheduled date only, never agenda publication date."""
    soup=BeautifulSoup(html,"html.parser")
    found={}
    for heading in soup.select("h3.meeting-title-heading"):
        if "planning and development committee" not in _text(heading).lower():
            continue
        label=(heading.find(attrs={"aria-label":True}) or heading).get("aria-label","")
        date=""
        m=re.search(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
                    r"([A-Za-z]+)\s+(\d{1,2}),?\s+(20\d{2})",label,re.I)
        if m:
            try:date=datetime.strptime(" ".join(m.groups()),"%B %d %Y").date().isoformat()
            except ValueError:pass
        container=heading
        for depth in range(7):
            container=container.parent
            if container is None or container.name in ("html","body"):break
            matches={meeting_id(_link(BRAMPTON_CALENDAR,a["href"]))
                     for a in container.find_all("a",href=True)
                     if "/Meeting" in a["href"]}
            matches.discard("")
            if len(matches)==1:
                found[next(iter(matches))]=date
                break
    return found


def brampton_records(session,max_meetings=16):
    calendar=fetch(session,BRAMPTON_CALENDAR)
    meetings=parse_calendar(calendar)
    dates=_brampton_calendar_dates(calendar)
    # This calendar can include past/future meetings; the most recent visible
    # 16 are a review WINDOW, never completeness of Council records.
    selected=list(meetings.items())[:max_meetings]
    all_records=[]
    agenda_ok=0
    calendar_only=0
    for key,url in selected:
        try:
            agenda=parse_meeting_agenda(fetch(session,url),url)
            all_records.extend(agenda)
            agenda_ok+=1
        except (RuntimeError,requests.RequestException,ValueError):
            # eSCRIBE Meeting.aspx currently renders a JavaScript shell
            # without agenda item descriptions to ordinary GET. Do NOT
            # fabricate applications. Save only the public meeting signal.
            calendar_only+=1
            all_records.append(dict(
                source_id="brampton_planning_agendas",
                record_id=key+"|CALENDAR_ONLY",
                title="Brampton Planning and Development Committee public meeting",
                site="",company="",company_role="NOT_AN_APPLICATION_OR_BUYER",
                stage="PDC_CALENDAR_AGENDA_NOT_READABLE",
                signal_type="OFFICIAL_MEETING_SCHEDULE_ONLY",
                source_date="",date_basis="MEETING_DATE_NOT_PUBLIC_POST_DATE",
                source_url=url,description="",
                commercial_fit="USE_UNKNOWN",procurement_status="UNKNOWN",
                verification="CALENDAR_LINK_ONLY_NO_APPLICATION_EXTRACTED",
                attributes={"meeting_date":dates.get(key,""),
                            "meeting_id":key,"agenda_data_verified":False}))
    unique={(r["source_id"],r["record_id"]):r for r in all_records}
    if not unique:raise RuntimeError("No published Brampton PDC calendar entries")
    return list(unique.values()),{"discovered":len(meetings),"fetched":len(selected),
               "agenda_parsed":agenda_ok,"calendar_only":calendar_only}


def run(data_dir="data",out_dir="GTA_RADAR_RESULTS",source=None,session=None,now=None):
    selected=set(source or SOURCES)
    if not selected or selected-set(SOURCES):raise ValueError("Unknown source")
    session=session or requests.Session()
    now=now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    data_dir=Path(data_dir);out_dir=Path(out_dir)
    data_dir.mkdir(parents=True,exist_ok=True);out_dir.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(data_dir/"early_discovery_review.sqlite")
    db_setup(db)
    status=[]
    try:
        for source_id in SOURCES:
            if source_id not in selected:continue
            try:
                if source_id=="burlington_ward_discovery":
                    records,stats=burlington_records(session)
                    coverage="OFFICIAL_LINKED_WARD_PROJECT_PAGES"
                    blocked=stats.get("blocked_details",[])
                    _write_csv(out_dir/"EARLY_BURLINGTON_BLOCKED_DETAILS.csv",
                         BURLINGTON_BLOCKED,
                         [{"source_url":u,"problem":e,
                           "impact":"REVIEW_ONLY_NOT_RETRIEVED_OR_NEW"}
                          for u,e in blocked])
                    if blocked:
                        # Complete-source snapshot is deliberately NOT updated.
                        # The records remain visible only in a separate
                        # review file, never emitted as fresh change events.
                        _write_csv(out_dir/"EARLY_BURLINGTON_PARTIAL_REVIEW.csv",
                          FIELDS,[dict(x,first_seen_at="",last_seen_at="",
                             current_snapshot_status="PARTIAL_SOURCE_UNCOMMITTED",
                             not_sale_ready_reason="SOME_OFFICIAL_PAGES_403") for x in records])
                        status.append(dict(source_id=source_id,status="PARTIAL_UNCOMMITTED",
                             fetched=len(records),new=0,updated=0,baseline="NO",
                             discovered_pages=stats["discovered"],
                             fetched_pages=stats["fetched"],coverage="INCOMPLETE_DETAIL_ACCESS",
                             warning=f"{len(blocked)}_PAGES_INACCESSIBLE;NO_FALSE_NEW_EVENTS",
                             error=""))
                        continue
                else:
                    records,stats=brampton_records(session)
                    coverage="PDC_AGENDA_APPLICATION_ITEMS" if not stats["calendar_only"] else "PDC_CALENDAR_AND_PARTIAL_AGENDAS"
                saved=save_source(db,source_id,records,now)
                state=("PARTIAL_CALENDAR_ONLY" if source_id=="brampton_planning_agendas"
                   and stats.get("calendar_only",0)>0 else "SUCCESS")
                status.append(dict(source_id=source_id,status=state,
                     fetched=len(records),discovered_pages=stats["discovered"],
                     fetched_pages=stats["fetched"],coverage=coverage,
                     warning=("AGENDA_ITEMS_UNAVAILABLE;CALENDAR_ONLY_NO_PROJECT_LEADS"
                              if state=="PARTIAL_CALENDAR_ONLY" else
                              "NO_OPEN_PROCUREMENT_VERIFIED;PUBLICATION_DATE_UNKNOWN"),
                     error="",**saved))
            except (RuntimeError,ValueError,requests.RequestException,sqlite3.Error) as err:
                db.rollback()
                status.append(dict(source_id=source_id,status="FAILED",
                     fetched=0,new=0,updated=0,baseline="NO",coverage="UNVERIFIED",
                     discovered_pages=0,fetched_pages=0,warning="SOURCE_FAILURE_NOT_ZERO",
                     error=str(err)[:240]))
        queue=[]
        seen_ok={s["source_id"] for s in status if s["status"]=="SUCCESS"}
        for sid,rid,first,last,raw in db.execute(
             "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots"):
            if sid not in SOURCES:continue
            item=json.loads(raw)
            if item["commercial_fit"] not in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"):continue
            queue.append(dict(item,first_seen_at=first,last_seen_at=last,
                current_snapshot_status=("SOURCE_FAILED" if sid not in seen_ok else
                 "SEEN_ON_LAST_SUCCESS" if last==now else "HISTORICAL_NOT_LATEST_PAGE"),
                not_sale_ready_reason="BUYER_UNVERIFIED;VENDORS_UNKNOWN;POSTING_DATE_UNKNOWN"))
        queue.sort(key=lambda x:(x.get("stage",""),x.get("title","")))
        changes=[dict(json.loads(raw),observed_at=obs,source_id=sid,
                      record_id=rid,change_type=typ)
                 for obs,sid,rid,typ,raw in db.execute(
                   "SELECT observed_at,source_id,record_id,change_type,content "
                   "FROM changes WHERE observed_at=?",(now,))]
        _write_csv(out_dir/"EARLY_DISCOVERY_SOURCE_STATUS.csv",STATUS,status)
        _write_csv(out_dir/"EARLY_DISCOVERY_RESEARCH_QUEUE.csv",FIELDS,queue)
        _write_csv(out_dir/"EARLY_DISCOVERY_CHANGES_REVIEW_ONLY.csv",CHANGES,changes)
        for s in status:
            print(s["source_id"],s["status"],"records",s["fetched"],
                  "post-baseline changes",s["new"]+s["updated"],flush=True)
        print("Zero paid AI; historic baseline never NEW leads")
        return 1 if any(s["status"]=="FAILED" for s in status) else 0
    finally:db.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",action="append",choices=SOURCES)
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args(argv)
    return run(a.data_dir,a.output_dir,a.source)


if __name__=="__main__":raise SystemExit(main())
