"""Four high-value early-investment lanes, free publisher evidence only.

Feeds are bounded, independently baselined, and fail closed. None proves a
purchase is unawarded or a named company is the procurement decision-maker.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from early_cue_watch import db_setup, save_source, _write_csv

FEEDS = {
    "feddev_investment": {
        "url": ("https://api.io.canada.ca/io-server/gc/news/en/v2?"
                "atomtitle=Federal+Economic+Development+Agency+for+Southern+Ontario"
                "&dept=economicdevelopmentsouthernontario&format=atom&orderBy=desc"
                "&pick=50&publishedDate%3E=2026-01-01&sort=publishedDate&type=newsreleases"),
        "coverage": "LATEST_50_FEDDEV_NEWS_RELEASES_NOT_COMPLETE_RECIPIENT_LIST",
    },
    "investontario_investment": {
        "url": "https://www.investontario.ca/press-room",
        "coverage": "PUBLIC_PRESS_ROOM_INDEX_VISIBLE_LINKS_ONLY",
    },
    "corporate_capex_watch": {
        "url": "https://www.mapleleaffoods.com/news/",
        "coverage": "MAPLE_LEAF_FOODS_NEWS_ONLY_NOT_ALL_COMPANIES",
    },
    "industrial_property_watch": {
        "url": "https://www.altusgroup.com/research/cre-this-week-in-canada/",
        "coverage": "ALTUS_PUBLIC_WEEKLY_TRANSACTION_CONTEXT_NOT_LEASES_EXHAUSTIVE",
    },
}
SOURCES=tuple(FEEDS)
ALLOWED={"api.io.canada.ca","www.canada.ca","feddev-ontario.canada.ca",
         "www.investontario.ca","investontario.ca","www.magna.com",
         "www.altusgroup.com","www.oxfordproperties.com","www.mapleleaffoods.com"}
DATE=re.compile(r"\b(20\d\d[-/]\d\d[-/]\d\d)\b")
INVESTMENT=re.compile(r"\b(?:invest(?:ment|ing|s)?|expand\w*|expansion|moderniz\w*|"
    r"production|manufactur\w*|automati\w*|industrial|equip\w*|new (?:facility|plant|"
    r"warehouse|factory)|capital expenditure|capex|build(?:ing)?|distribution cent(?:re|er)|"
    r"retrofit|relocat\w*|facility upgrade|construction|retool\w*)\b",re.I)
PROPERTY=re.compile(r"\b(?:industrial|manufactur\w*|warehouse|distribution|logistic\w*|"
    r"lease|tenant|facility|sq\.?\s*ft|square feet|acre|logistics|property)\b",re.I)
GEO=re.compile(r"\b(?:Brampton|Mississauga|Toronto|Vaughan|Markham|Richmond Hill|"
    r"Burlington|Oakville|Milton|Pickering|Ajax|Whitby|Oshawa|Scarborough|"
    r"Etobicoke|Caledon|Newmarket|Aurora|Hamilton|Waterloo|Kitchener|Cambridge|"
    r"Guelph|Brantford|St\.? Catharines|Niagara|Woodbridge|Concord|Keswick|"
    r"York Region|Durham|Peel|Halton)\b",re.I)
FIELDS=("source_id","record_id","title","site","company","company_role", "stage",
        "source_date","date_basis","source_url","signal_type","description",
        "commercial_fit","geographic_confidence","procurement_status","verification",
        "purchase_hypothesis","source_scope","project_cost","funding_contribution")
STATUS=("source_id","status","fetched","new","updated","baseline","coverage","error")
CHANGES=("observed_at","source_id","record_id","change_type",*FIELDS[2:])


def _clean(text):
    return " ".join(str(text or "").split())


def _allowed(url):
    p=urlparse(url)
    return p.scheme=="https" and p.hostname in ALLOWED and p.username is None and p.password is None


def _fetch(session,url,*,xml=False):
    if not _allowed(url):raise ValueError("Unapproved publisher domain or insecure URL")
    r=session.get(url,headers={"User-Agent":"GTA-Radar-PublicInvestmentResearch/0.1"},timeout=(10,45))
    r.raise_for_status()
    raw=r.content
    if not 120<len(raw)<2_000_000:raise RuntimeError("Empty or oversize publisher response")
    if xml:
        if not (b"<feed" in raw[:500] or b"<rss" in raw[:500]):
            raise RuntimeError("Publisher feed returned unexpected document")
    elif "<html" not in r.text[:6000].lower() and "<!doctype html" not in r.text[:6000].lower():
        raise RuntimeError("Publisher returned non-HTML page")
    return raw if xml else r.text


def _record(sid,url,title,desc="",company="",published="",scope=""):
    title=_clean(title)[:280];desc=_clean(desc)[:1100];company=_clean(company)[:150]
    text=title+" "+desc
    if not _allowed(url) or not title:raise ValueError("Invalid project source URL or title")
    fit=("POSSIBLE_COMMERCIAL" if INVESTMENT.search(text) else "USE_UNKNOWN")
    # A generic market story, even one naming a city, cannot prove tenant spend.
    if sid=="industrial_property_watch":fit="LOW"  # Market summaries are not tenant purchasing events.
    if sid=="corporate_capex_watch":fit="LOW"  # Requires named, dated, local capex in full article.
    if sid=="feddev_investment":fit="REVIEW" if company and INVESTMENT.search(text) else "LOW"
    if sid=="investontario_investment":fit="REVIEW" if INVESTMENT.search(text) else "LOW"
    published=published[:10] if DATE.fullmatch(published[:10]) else ""
    return dict(source_id=sid,record_id=url,title=title,site="",company=company,
       company_role=("PUBLIC_COMPANY_MENTION_NOT_VERIFIED_PURCHASER" if company
                     else "COMPANY_NOT_STRUCTURED_IN_INDEX"),stage="PUBLIC_ANNOUNCEMENT",
       source_date=published,date_basis="PUBLISHER_DATE_IF_PRESENT" if published else "NOT_VERIFIED",
       source_url=url,signal_type=("INDUSTRIAL_PROPERTY_CONTEXT" if sid=="industrial_property_watch"
                                else "CORPORATE_FINANCIAL_ANNOUNCEMENT" if sid=="corporate_capex_watch"
                                else "CAPITAL_INVESTMENT_ANNOUNCEMENT"),
       description=desc,commercial_fit=fit,
       geographic_confidence="SOUTHERN_ONTARIO_TEXT_MENTION_NOT_SITE_VERIFIED" if GEO.search(text)
                            else "LOCATION_UNVERIFIED_OR_OUTSIDE_GTA",
       procurement_status="UNKNOWN",verification="PUBLISHED_DOCUMENT_NOT_UNAWARDED_PURCHASE",
       purchase_hypothesis="RESEARCH_ONLY_NOT_CONFIRMED_PURCHASE",source_scope=scope,
       project_cost="",funding_contribution="")


def parse_feddev_atom(raw):
    """Atom links, not a claim that RSS releases contain individual recipients."""
    try:root=ET.fromstring(raw)
    except ET.ParseError as e:raise RuntimeError("Malformed FedDev Atom") from e
    if not root.tag.endswith("feed"):raise RuntimeError("FedDev feed element missing")
    items=[]
    for entry in root.findall("{*}entry"):
        title=entry.findtext("{*}title") or ""
        detail=(entry.findtext("{*}summary") or entry.findtext("{*}content") or "")
        detail=BeautifulSoup(detail,"html.parser").get_text(" ",strip=True)
        date=(entry.findtext("{*}published") or entry.findtext("{*}updated") or "")[:10]
        urls=[n.attrib.get("href","") for n in entry.findall("{*}link") if n.attrib.get("rel","alternate")=="alternate"]
        urls.extend(n.attrib.get("href","") for n in entry.findall("{*}link"))
        url=next((u for u in urls if u.startswith("https://www.canada.ca/en/economic-development-southern-ontario/news/")),"")
        if not url:continue
        items.append(_record("feddev_investment",url,title,detail,published=date,
                             scope=FEEDS["feddev_investment"]["coverage"]))
    if not items:raise RuntimeError("FedDev feed has no supported news links")
    return list({r['record_id']:r for r in items}.values())


def _article_links(html,base,allowed_prefixes):
    soup=BeautifulSoup(html,"html.parser")
    links={}
    for a in soup.select("a[href]"):
        url=urljoin(base,a.get("href","" )).split("#",1)[0]
        if not _allowed(url):continue
        if not any(urlparse(url).path.lower().startswith(p) for p in allowed_prefixes):continue
        title=_clean(a.get('aria-label') or a.get('title') or a.get_text(" ",strip=True))
        if title.lower() in ('read more','learn more','view article','details') or len(title)<15:
            # Several publisher cards link "Read more" separately from the
            # actual h4/h5 headline. Do not turn that into a fake project.
            for node in (a.parent,a.parent.parent if a.parent else None,
                         a.parent.parent.parent if a.parent and a.parent.parent else None):
                if not node:continue
                h=node.find(['h2','h3','h4','h5','h6'])
                if h:
                    headline=_clean(h.get_text(' ',strip=True))
                    if 15<len(headline)<300:title=headline;break
        title=re.sub(r'^Read More\s*[-–:]\s*','',title,flags=re.I)
        if len(title)<15 or len(title)>300:continue
        if url not in links or len(title)>len(links[url]):links[url]=title
    return links


def title_entity(title):
    """Company visible in official headline, NOT a verified procurement buyer."""
    value=_clean(title)
    patterns=(
       r"^Invest Ontario welcomes (.+?)(?:[’']s? |\s+expansion|\s+to |\s+in )",
       r"^(.{3,90}?)\s+(?:to build|to open|establishes|is investing|announces|expands)\b",
    )
    for expr in patterns:
        m=re.search(expr,value,re.I)
        if m:
            name=m.group(1).strip(' -.,')
            if 4<len(name)<90:return name
    return ''


def parse_investontario(html):
    links=_article_links(html,FEEDS["investontario_investment"]["url"],
                         ("/press-release/",))
    if not links:raise RuntimeError("Invest Ontario visible press release links not found")
    return [_record("investontario_investment",url,title,
                    company=title_entity(title),scope=FEEDS["investontario_investment"]["coverage"])
            for url,title in links.items()]


MONTH_DATE=re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\b",re.I)
SPECIFIC_SPEND=re.compile(r"\b(?:invest(?:ing|ment)?\s+\$|\$[\d,.]+\s*(?:million|billion)|\bnew\s+(?:factory|production line|manufacturing facility)|\binstall(?:ing|ation)?\s+(?:new\s+)?(?:machinery|equipment)|\b(?:equipment|facility)\s+upgrades?)\b",re.I)

def _published_date(soup):
    """Only official publication metadata or a date in the opening article text."""
    for attr,key in (("property","article:published_time"),("name","date"),
                     ("name","datePublished"),("name","dcterms.date")):
        tag=soup.find("meta",attrs={attr:key})
        if tag:
            value=(tag.get("content") or "")[:10]
            if DATE.fullmatch(value):return value.replace('/','-')
    for tag in soup.find_all('time',limit=4):
        value=(tag.get('datetime') or '')[:10]
        if DATE.fullmatch(value):return value.replace('/','-')
    main=soup.find('main') or soup.find('article') or soup
    opening=_clean(main.get_text(' ',strip=True))[:2800]
    m=MONTH_DATE.search(opening)
    if m:
        try:return datetime.strptime(' '.join(m.groups()),'%B %d %Y').date().isoformat()
        except ValueError:pass
    return ''


def _index_date(link):
    """Use date in a single press-release card, never a whole page date."""
    node=link
    for _ in range(5):
        node=node.parent
        if node is None or node.name in ('body','html'):break
        others={urljoin(FEEDS['investontario_investment']['url'],a['href'])
                for a in node.select('a[href]') if '/press-release/' in a['href']}
        if len(others)>1:break
        if len(_clean(node.get_text(' ',strip=True)))>850:break
        date=_published_date(node)
        if date:return date
    return ''


def enriched_investontario(session,html,max_details=32):
    """Extract index dates first, then verify recent individual article details."""
    items=parse_investontario(html)
    soup=BeautifulSoup(html,'html.parser')
    links={}
    for anchor in soup.select('a[href]'):
        url=urljoin(FEEDS['investontario_investment']['url'],anchor.get('href','')).split('#',1)[0]
        if url not in links and any(item['source_url']==url for item in items):
            links[url]=anchor
    for row in items:
        if row['source_url'] in links:
            date=_index_date(links[row['source_url']])
            if date:row['source_date']=date;row['date_basis']='OFFICIAL_INDEX_CARD_DATE'
    for row in items[:max_details]:
        try:
            body=_fetch(session,row['source_url'])
            detail=BeautifulSoup(body,'html.parser')
            heading=detail.find('h1')
            if heading:
                actual=_clean(heading.get_text(' ',strip=True))
                if len(actual)>12:row['title']=actual[:280]
            main=detail.find('main') or detail
            snippets=[]
            for para in main.find_all('p')[:20]:
                value=_clean(para.get_text(' ',strip=True))
                if INVESTMENT.search(value):snippets.append(value)
                if len(snippets)>=3:break
            if snippets:row['description']=' '.join(snippets)[:1100]
            date=_published_date(detail)
            if date:row['source_date']=date;row['date_basis']='OFFICIAL_ARTICLE_PUBLICATION_DATE'
            candidate=title_entity(row['title'])
            if candidate:row['company']=candidate
            if row['company']:
                row['company_role']='PUBLIC_ANNOUNCEMENT_ENTITY_NOT_VERIFIED_PURCHASER'
            text=row['title']+' '+row['description']
            row['geographic_confidence']=('SOUTHERN_ONTARIO_TEXT_MENTION_NOT_SITE_VERIFIED'
                  if GEO.search(text) else 'LOCATION_UNVERIFIED_OR_OUTSIDE_GTA')
            row['commercial_fit']='REVIEW' if (row['company'] and row['source_date']
                    and GEO.search(text) and SPECIFIC_SPEND.search(text)) else 'LOW'
        except (requests.RequestException,ValueError,RuntimeError):
            # Keep index data and verified dates, but do not claim a project.
            row['commercial_fit']='LOW'
    for row in items[max_details:]:
        row['commercial_fit']='LOW'  # Index-only announcements are not yet actionable.
    return items


def parse_corporate(html):
    links=_article_links(html,FEEDS["corporate_capex_watch"]["url"],
                         ("/news/",))
    if not links:raise RuntimeError("Maple Leaf Foods news index unavailable; no false success")
    return [_record("corporate_capex_watch",url,title,company="Maple Leaf Foods",
                    scope=FEEDS["corporate_capex_watch"]["coverage"]) for url,title in links.items()]


def enriched_corporate(session,html,max_details=12):
    items=parse_corporate(html)
    for row in items[:max_details]:
        try:
            detail=BeautifulSoup(_fetch(session,row['source_url']),'html.parser')
            main=detail.find('main') or detail
            paras=[_clean(p.get_text(' ',strip=True)) for p in main.find_all('p')[:15]]
            row['description']=' '.join(p for p in paras if INVESTMENT.search(p))[:1100]
            row['source_date']=_published_date(detail)
            row['date_basis']='OFFICIAL_ARTICLE_PUBLICATION_DATE' if row['source_date'] else 'NOT_VERIFIED'
            text=row['title']+' '+row['description']
            if row['source_date'] and GEO.search(text) and SPECIFIC_SPEND.search(text):
                row['commercial_fit']='REVIEW'
                row['geographic_confidence']='SOUTHERN_ONTARIO_TEXT_MENTION_NOT_SITE_VERIFIED'
        except (requests.RequestException,ValueError,RuntimeError):pass
    return items

def parse_property(html):
    """Altus weekly published transaction context, NOT an inferred tenant."""
    soup=BeautifulSoup(html,"html.parser")
    main=soup.find("main") or soup
    # Page may display only reports and no transaction table in static HTML.
    text=_clean(main.get_text(" ",strip=True))
    if "commercial" not in text.lower() and "industrial" not in text.lower():
        raise RuntimeError("No industrial/property section in Altus page")
    # Stable first-seen watch of source revisions. A report isn't a new lease.
    # Persist a meaningful digest fragment without volatile site footer details.
    rows=[]
    for h in main.find_all(["h2","h3","h4"]):
        heading=_clean(h.get_text(" ",strip=True))
        if not PROPERTY.search(heading) or len(heading)<12:continue
        content=_clean(h.parent.get_text(" ",strip=True))[:650]
        if not PROPERTY.search(content):continue
        url=FEEDS["industrial_property_watch"]["url"]
        row=_record("industrial_property_watch",url,heading,content,
                    scope=FEEDS["industrial_property_watch"]["coverage"])
        row['record_id']=url+"#"+re.sub(r'[^a-z0-9]+','-',heading.lower()).strip('-')[:75]
        rows.append(row)
    if not rows:raise RuntimeError("Altus public transaction subheadings not parsable")
    return list({r['record_id']:r for r in rows}.values())[:30]


def parse_feddev_backgrounder(html,url,release_date=""):
    """Recipient, project and financials from the official FedDev table only."""
    soup=BeautifulSoup(html,"html.parser")
    items=[]
    for table in soup.find_all('table'):
        headings=[_clean(t.get_text(' ',strip=True)).lower() for t in table.find_all('th')]
        if not any('recipient' in h or 'business name' in h for h in headings):continue
        if not any('project' in h for h in headings):continue
        for tr in table.find_all('tr'):
            cells=tr.find_all('td',recursive=False)
            if len(cells)<2:continue
            company=_clean(cells[0].get_text(' ',strip=True))[:150]
            project=_clean(cells[1].get_text(' ',strip=True))[:1100]
            if not (3<=len(company)<=140 and len(project)>=20):continue
            row=_record('feddev_investment',url,'FedDev project: '+company,project,
                        company=company,published=release_date,
                        scope='OFFICIAL_RECIPIENT_ROW_NOT_PROCUREMENT')
            row['record_id']=url+'#recipient-'+re.sub(r'[^a-z0-9]+','-',company.lower()).strip('-')[:120]
            row['date_basis']='RELATED_RELEASE_DATE_NOT_PURCHASE_COMMITMENT_DATE'
            row['project_cost']=_clean(cells[2].get_text(' ',strip=True)) if len(cells)>2 else ''
            row['funding_contribution']=_clean(cells[3].get_text(' ',strip=True)) if len(cells)>3 else ''
            row['commercial_fit']='REVIEW' if INVESTMENT.search(project) else 'LOW'
            row['geographic_confidence']=('SOUTHERN_ONTARIO_TEXT_MENTION_NOT_SITE_VERIFIED'
                if GEO.search(project) else 'LOCATION_UNVERIFIED_OR_OUTSIDE_GTA')
            items.append(row)
    return list({r['record_id']:r for r in items}.values())


def enriched_feddev(session,feed,max_releases=28):
    """Follow official backgrounders; never invent recipient companies."""
    releases=parse_feddev_atom(feed)
    expanded={}
    visited=set()
    for release in releases[:max_releases]:
        if not re.search(r'business|compan|recipient|funding|support|investment',release['title'],re.I):
            continue
        try:
            html=_fetch(session,release['source_url'])
            for item in parse_feddev_backgrounder(html,release['source_url'],release['source_date']):
                expanded[item['record_id']]=item
            soup=BeautifulSoup(html,'html.parser')
            urls=[]
            for link in soup.find_all('a',href=True):
                label=_clean(link.get_text(' ',strip=True)).lower()
                url=urljoin(release['source_url'],link['href']).split('#',1)[0]
                if not (_allowed(url) and url.startswith('https://www.canada.ca/en/economic-development-southern-ontario/news/')):
                    continue
                if ('backgrounder' in label or 'backgrounder' in url.lower()
                   or ('recipient' in label and 'project' in label)):
                    urls.append(url)
            for url in dict.fromkeys(urls[:4]):
                if url in visited:continue
                visited.add(url)
                try:
                    for item in parse_feddev_backgrounder(_fetch(session,url),url,release['source_date']):
                        expanded[item['record_id']]=item
                except (requests.RequestException,ValueError,RuntimeError):continue
        except (requests.RequestException,ValueError,RuntimeError):continue
    return releases+list(expanded.values())


PARSERS={"feddev_investment":parse_feddev_atom,
         "investontario_investment":parse_investontario,
         "corporate_capex_watch":parse_corporate,
         "industrial_property_watch":parse_property}


def run(data_dir="data",output_dir="GTA_RADAR_RESULTS",sources=None,session=None,observed=None):
    selected=set(sources or SOURCES)
    if not selected or selected-set(SOURCES):raise ValueError("Unknown source")
    data=Path(data_dir);out=Path(output_dir)
    data.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    session=session or requests.Session()
    stamp=observed or datetime.now(timezone.utc).isoformat(timespec="seconds")
    db=sqlite3.connect(data/"early_investment_watches.sqlite")
    db_setup(db)
    statuses=[]
    try:
        for sid in SOURCES:
            if sid not in selected:continue
            try:
                raw=_fetch(session,FEEDS[sid]['url'],xml=(sid=="feddev_investment"))
                records=(enriched_feddev(session,raw) if sid=="feddev_investment" else
                         enriched_investontario(session,raw) if sid=="investontario_investment" else
                         enriched_corporate(session,raw) if sid=="corporate_capex_watch" else
                         PARSERS[sid](raw))
                # Enriching an older indexed article or discovering an old
                # funded recipient cannot be counted as a new investment cue.
                earliest=db.execute('SELECT MIN(first_seen_at) FROM snapshots WHERE source_id=?',
                                    (sid,)).fetchone()[0]
                if earliest:
                    for record in records:
                        if record['source_date'] and record['source_date']<earliest[:10]:
                            record['source_scope']='HISTORICAL_PUBLICATION_BACKFILL_NOT_FRESH'
                result=save_source(db,sid,records,stamp)
                statuses.append(dict(source_id=sid,status="SUCCESS",fetched=len(records),
                    coverage=FEEDS[sid]["coverage"],error="",**result))
            except (requests.RequestException,ValueError,RuntimeError,ET.ParseError,sqlite3.Error) as exc:
                db.rollback()
                statuses.append(dict(source_id=sid,status="FAILED",fetched=0,new=0,
                    updated=0,baseline="NO",coverage="NOT_VERIFIED",error=(type(exc).__name__+': '+str(exc))[:240]))
        good={x['source_id'] for x in statuses if x['status']=="SUCCESS"}
        events=[]
        for date,kind,sid,rid,raw in db.execute(
            "SELECT observed_at,change_type,source_id,record_id,content FROM changes WHERE observed_at=?",
            (stamp,)):
            if sid not in good:continue
            record=json.loads(raw)
            if record.get('source_scope')=='HISTORICAL_PUBLICATION_BACKFILL_NOT_FRESH':
                continue
            events.append(dict(record,observed_at=date,change_type=kind))
        research=[]
        for sid,rid,first,last,raw in db.execute(
            "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots"):
            row=json.loads(raw)
            if row['commercial_fit'] not in ('REVIEW','POSSIBLE_COMMERCIAL'):continue
            research.append(dict(row,first_seen_at=first,last_seen_at=last,
                    current_snapshot_status=("SOURCE_FAILED" if sid not in good else
                        "OBSERVED_LATEST" if last==stamp else "OLDER_OR_OUTSIDE_WINDOW")))
        _write_csv(out/'EARLY_INVESTMENT_SOURCE_STATUS.csv',STATUS,statuses)
        _write_csv(out/'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv',CHANGES,events)
        _write_csv(out/'EARLY_INVESTMENT_RESEARCH_QUEUE.csv',
                   (*FIELDS,'first_seen_at','last_seen_at','current_snapshot_status'),research)
        context=[]
        for sid,rid,first,last,raw in db.execute(
            'SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots'):
            row=json.loads(raw)
            if row['commercial_fit'] not in ('REVIEW','POSSIBLE_COMMERCIAL'):
                context.append(dict(row,first_seen_at=first,last_seen_at=last))
        _write_csv(out/'EARLY_INVESTMENT_CONTEXT_ONLY.csv',
                   (*FIELDS,'first_seen_at','last_seen_at'),context)
        for row in statuses:
            print(row['source_id'],row['status'],'records',row['fetched'],
                  'postbaseline',row['new']+row['updated'],flush=True)
        return 1 if any(row['status']=='FAILED' for row in statuses) else 0
    finally:db.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',default='data')
    p.add_argument('--output-dir',default='GTA_RADAR_RESULTS')
    p.add_argument('--source',choices=SOURCES,action='append')
    args=p.parse_args(argv)
    return run(args.data_dir,args.output_dir,args.source)

if __name__=='__main__':raise SystemExit(main())
