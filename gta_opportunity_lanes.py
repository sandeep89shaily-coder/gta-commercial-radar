"""Separate evidence-gated private development and government procurement queues.

Consumes existing verified source outputs, uses no network/AI, never changes
collector ledgers. Private ≠ government; index-only and historical records
are explicitly labelled. No source-backed name/contact = UNKNOWN.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

PRIVATE_TOP="GTA_RADAR_PRIVATE_TOP_10.csv"
PRIVATE_ALL="GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv"
PRIVATE_CHANGES="GTA_RADAR_PRIVATE_CHANGES_TO_VERIFY.csv"
PRIVATE_FRESH="GTA_RADAR_PRIVATE_VERIFIED_FRESH.csv"
PRIVATE_REJECTED="GTA_RADAR_PRIVATE_EXCLUDED.csv"
GOV_TOP="GTA_RADAR_GOVERNMENT_TOP_10.csv"
GOV_CHANGES="GTA_RADAR_GOVERNMENT_CHANGES_TO_VERIFY.csv"
STATUS="GTA_RADAR_OPPORTUNITY_LANES_STATUS.json"
DASHBOARD="GTA_RADAR_OPPORTUNITY_LANES.html"
FIELDS=("rank","opportunity_id","lane","city","address","project_name",
        "nature_of_work","project_stage","stage_gate","private_ownership_evidence",
        "company_name","company_evidence","contact_name","contact_role",
        "phone","email","contact_status","application_ids","first_seen_local",
        "observation","source_date","date_basis","freshness_class",
        "source_types","source_urls","commercial_use_cases","estimated_value",
        "procurement_status","score","reason","next_action")
FILES={
    "private_notice":"GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv",
    "private_master":"GTA_RADAR_COLLECTION_MASTER.csv",
    "private_municipal":"GTA_RADAR_MUNICIPAL_PROJECT_FEED.csv",
    "private_daily":"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",
    "private_qualified":"GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv",
    "private_gis":"GTA_RADAR_BURLINGTON_GIS_PROJECTS.csv",
    "government":"GTA_RADAR_REGIONAL_COMMERCIAL_REVIEW.csv",
    "government_changes":"GTA_RADAR_REGIONAL_COMMERCIAL_CHANGES_TO_REVIEW.csv",
    "government_excluded":"GTA_RADAR_REGIONAL_COMMERCIAL_EXCLUDED.csv",
}
PRIVATE_SCOPE=re.compile(
    r"\b(?:industrial|warehouse|warehousing|logistics|distribution|"
    r"manufactur\w*|factory|self.storage|storage.facility|commercial|retail|"
    r"shop(?:ping)?|office|hotel|restaurant|food.processing|gas station|"
    r"mixed.use|daycare|clinic|medical|business park|light.industrial|"
    r"data.cent(?:re|er)|auto(?:motive)? repair|industrial renovation)\b",re.I)
PRIORITY_SCOPE=re.compile(
    r"\b(?:industrial|warehouse|logistics|distribution|manufactur\w*|"
    r"factory|hotel|self.storage|data.cent(?:re|er)|mixed.use)\b",re.I)
PUBLIC_OWNER=re.compile(
    r"\b(?:region of|regional municipality|city of|town of|township of|"
    r"government of|ontario ministry|public school board|"
    r"metrolinx|toronto water|solid waste management services|"
    r"municipal (?:capital|infrastructure)|public works department)\b",re.I)
CLOSED=re.compile(r"\b(?:withdrawn|refused|rejected|cancelled|canceled|"
                  r"closed|inactive|omb approved|olt approved|"
                  r"construction completed|work completed)\b",re.I)
PAUSED=re.compile(r"\b(?:appeal(?:ed)?|on hold|suspended|deferred|postponed)\b",re.I)
CURRENT_DESIGN=re.compile(r"\b(?:under review|site plan|planning|"
    r"zoning|official plan amendment|pre.application|submitted|proposed)\b",re.I)
PERMIT=re.compile(r"\b(?:permit (?:issued|applied|under review)|"
                  r"conditional permit|alteration|renovation|addition)\b",re.I)
COMPANY_END=re.compile(r"\b(?:Inc\.?|Ltd\.?|Limited|Corporation|Corp\.?|"
                       r"Developments?|Industrial|Realty|REIT|Holdings?)\b",re.I)
PUBLICATION_BASIS=re.compile(
    r"(?:VERIFIED_FIRST_PUBLICATION|OFFICIAL_FIRST_PUBLICATION|"
    r"OFFICIAL_NOTICE_PUBLICATION_DATE|PUBLISHER_POSTED_DATE)",re.I)

def _str(v):
    return " ".join(str(v or "").split())[:2400]

def _csv(path):
    if not path.is_file():return []
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def _valid(url):
    try:
        p=urlparse(str(url or ""))
        return (p.scheme=="https" and bool(p.hostname) and
                p.port in (None,443) and not p.username and not p.password)
    except ValueError:
        return False

def _links(v):
    return [x.strip() for x in re.split(r"\s*;\s*",str(v or ""))
            if _valid(x.strip())]

def _first(v):
    return next(iter(_links(v)),"")

def _site(v):
    # A civic site with a comma-suffixed city/postcode is the same parcel
    # as the shorter address used by municipal application feeds. Do not
    # truncate genuine multi-address titles (e.g. "1 Street, 6 & 8 Street").
    tokens=str(v or "").split(",")
    if len(tokens)>1 and re.match(r"^\s*(?:Brampton|Mississauga|Caledon|Toronto|Burlington|Oakville|Vaughan|Markham|Waterloo|Kitchener|Cambridge|Guelph|Hamilton)\b",tokens[1],re.I):
        v=tokens[0]
    text=_str(v).casefold().replace("boulevard","blvd").replace("road","rd")
    text=text.replace("drive","dr").replace("street","st").replace("avenue","ave")
    text=text.replace("court","ct").replace("highway","hwy")
    text=re.sub(r"\b(?:on|ontario|canada)\b"," ",text)
    return re.sub(r"[^a-z0-9]+","",text)

def _site_from_title(title):
    title=_str(title).split(" - ",1)[0]
    return title if re.search(r"\d",title) else ""

def _city(name,address=""):
    name=_str(name).title()
    # Some official Brampton permit feeds say "Peel" for the region.
    if name in ("Peel","Unknown",""):
        for city in ("Brampton","Mississauga","Caledon","Burlington",
                     "Toronto","Oakville","Vaughan","Kitchener"):
            if re.search(r"(?<!\w)"+city+r"(?!\w)",str(address),re.I):
                return city
    return name

def _private_item(source,row):
    if source=="private_notice":
        city=_city(row.get("city"))
        title=_str(row.get("project_title"))
        address=_str(row.get("address")) or _site_from_title(title)
        description=_str(row.get("description"))
        status=_str(row.get("current_status"))
        ident=_str(row.get("application_id"))
        urls=_links(row.get("record_source_url") or row.get("source_url"))
        observation=_str(row.get("observation"))
        firstseen=_str(row.get("first_seen_local"))
        date=_str(row.get("source_record_date"))
        basis=_str(row.get("date_basis"))
        kind="OFFICIAL_EXPLICIT_APPLICATION_ID"
        application_year=""
    elif source=="private_master":
        city=_city(row.get("city"),row.get("address"))
        title=""
        address=_str(row.get("address"))
        description=_str(row.get("description"))
        status=_str(row.get("current_status"))
        ident=_str(row.get("application_id"))
        urls=_links(row.get("evidence_urls"))
        observation=_str(row.get("observation"))
        firstseen=_str(row.get("first_seen_local"))
        date=_str(row.get("date"))
        basis=_str(row.get("date_basis"))
        kind=_str(row.get("record_kind"))
        application_year=_str(row.get("application_year_hint"))
    elif source=="private_municipal":
        city=_city(row.get("city"),row.get("address"))
        title=_str(row.get("project_title"))
        address=_str(row.get("address")) or _site_from_title(title)
        description=_str(row.get("description"))
        status=""
        ident=_str(row.get("application_id"))
        urls=_links(row.get("source_url"))
        observation=_str(row.get("observation"))
        firstseen=_str(row.get("first_seen_local"))
        date=""
        basis=""
        kind=_str(row.get("record_kind"))
        application_year=""
    elif source=="private_daily":
        city=_city(row.get("city"),row.get("address"))
        title=""
        address=_str(row.get("address"))
        description=_str(row.get("description"))
        status=_str(row.get("current_source_status"))
        ident=_str(row.get("project_id"))
        urls=_links(row.get("record_source_url"))
        observation=_str(row.get("observation"))
        firstseen=_str(row.get("first_seen_local"))
        date=_str(row.get("source_record_date"))
        basis=_str(row.get("date_basis"))
        kind="PERMIT_EVENT_OWNER_NOT_VERIFIED"
        application_year=""
    elif source=="private_qualified":
        # Existing V6 qualification already carries current source-backed
        # Brampton/Mississauga/Waterloo projects that the 16-city application
        # collection cannot always join. Never import AI company/contact claims
        # or a sale_ready flag from this *review-only* source.
        city=_city(row.get("city"),row.get("address"))
        title=""
        address=_str(row.get("address"))
        description=_str(row.get("qualification_scope") or row.get("description"))
        status=_str(row.get("official_status"))
        if _str(row.get("source_id")).endswith("building_permits"):
            if status.casefold()=="applied":status="Permit Applied"
            elif status.casefold()=="issued":status="Permit Issued"
        ident=_str(row.get("official_permit_id"))
        urls=_links(row.get("official_record_url") or row.get("record_source_url"))
        observation="HISTORICAL_OR_UNDATED_SOURCE_REVIEW"
        firstseen=""
        date=_str(row.get("source_record_date"))
        basis="OFFICIAL_APPLICATION_OR_PERMIT_EVENT_DATE_NOT_PUBLICATION"
        kind="SOURCE_BACKED_V6_REVIEW_NOT_BUYER_VERIFIED"
        application_year=date[:4] if re.match(r"20\d{2}-\d{2}-\d{2}$",date) else ""
    else:
        return None
    if not city or not urls or not (description or title):
        return None
    context=" ".join((title,description,status))
    if PUBLIC_OWNER.search(context):
        return dict(reject="PUBLIC_OWNER_OR_SCOPE",source=source)
    if not PRIVATE_SCOPE.search(context):
        return None
    if CLOSED.search(status) or re.search(r"\b(?:application withdrawn|project cancelled|"
                                          r"construction completed|inactive)\b",description,re.I):
        return dict(reject="INACTIVE_OR_CLOSED",source=source)
    if not (ident or address or title):
        return None
    company=""
    company_evidence=""
    # One project's title may explicitly identify the applicant after " - ".
    # A nearby GIS listing or a broker elsewhere on the street is not proof.
    if source=="private_notice" and " - " in title:
        proposal=title.rsplit(" - ",1)[1].strip()
        if COMPANY_END.search(proposal) and not PUBLIC_OWNER.search(proposal):
            company=proposal[:180]
            company_evidence="OFFICIAL_PROJECT_TITLE_NAMED_FIRM_ROLE_NOT_VERIFIED"
    if not company and source=="private_municipal":
        match=re.search(r"\b(?:application (?:made|submitted) by|applicant[: ])\s*"
                        r"([A-Z][\w .&,'()-]{5,110}?)(?=\s*(?:for |to |at |\.|;|$))",
                        description,re.I)
        if match and COMPANY_END.search(match.group(1)):
            company=_str(match.group(1))[:180]
            company_evidence="SOURCE_TEXT_NAMED_APPLICANT_ROLE_NOT_VERIFIED"
    private_evidence="PRIVATE_USE_INFERRED_OWNER_UNVERIFIED"
    return dict(city=city,address=address,title=title,description=description,
        status=status,application_id=ident,urls=urls,source=source,
        observation=observation,first_seen=firstseen,source_date=date,date_basis=basis,
        company=company,company_evidence=company_evidence,
        private_evidence=private_evidence,kind=kind,application_year=application_year)

def _group_private(rows):
    # One project, possibly multiple OPA/ZBA/Site Plan file numbers.
    # Site-specific grouping only, never 2 distinct streets or all city files.
    grouped=defaultdict(list)
    for r in rows:
        if "reject" in r:continue
        site=_site(r["address"]) or _site(_site_from_title(r["title"]))
        # Blank-address project-only signals generate duplicate rows for
        # Burlington; generic Toronto index URLs may also silently collapse
        # unrelated projects. Neither URL nor observation date is a site ID.
        if not site:
            continue
        grouped[(r["city"].casefold(),site)].append(r)
    return grouped

def _candidate(group,today):
    # Prefer source-specific detailed official project content over broad index.
    ranked=sorted(group,key=lambda r:(
        r["source"]=="private_notice",
        r["kind"] in ("APPLICATION_ID","OFFICIAL_EXPLICIT_APPLICATION_ID"),
        len(r["description"]),bool(r["company"])),reverse=True)
    best=ranked[0]
    descriptions=sorted({r["description"] for r in group if r["description"]},
        key=lambda x:len(x),reverse=True)
    scope=descriptions[0]
    statuses=[r["status"] for r in group if r["status"]]
    status=next((x for x in statuses if re.search("under review|submitted",x,re.I)),
         statuses[0] if statuses else "STAGE_NOT_VERIFIED")
    source_types=sorted({r["source"] for r in group})
    links=sorted({url for r in group for url in r["urls"]})
    apps=sorted({r["application_id"] for r in group
                  if r["application_id"] and r["kind"]!="PERMIT_EVENT_OWNER_NOT_VERIFIED"})
    company_source=next((r for r in ranked if r["company"]),None)
    company=company_source["company"] if company_source else ""
    company_evidence=company_source["company_evidence"] if company_source else ""
    location=best["address"] or best["title"]
    if PAUSED.search(status):
        stage_gate="APPEALED_OR_ON_HOLD"
    elif CLOSED.search(status):
        stage_gate="CLOSED_EXCLUDE"
    elif re.search(r"permit issued|NOAC Issued",status,re.I):
        stage_gate="PERMIT_OR_NOAC_ISSUED_VERIFY_PROCUREMENT"
    elif CURRENT_DESIGN.search(status) or any(r["source"]=="private_notice" for r in group):
        stage_gate="PLANNING_OR_SITE_PLAN_REVIEW"
    elif PERMIT.search(status+" "+scope):
        stage_gate="PERMIT_STAGE_VERIFY"
    else:
        stage_gate="STAGE_UNVERIFIED"
    years=[int(x[:4]) for x in (r["first_seen"] for r in group)
           if re.match(r"20\d{2}-\d\d-\d\d$",x)]
    first_seen=min((r["first_seen"] for r in group if re.match(r"20\d{2}-\d\d-\d\d$",r["first_seen"])),default="")
    flags={r["observation"] for r in group}
    observation=("RECORD_CHANGED" if "RECORD_CHANGED" in flags else
                 "FIRST_OBSERVED" if "FIRST_OBSERVED" in flags else
                 "INITIAL_BASELINE" if "INITIAL_BASELINE" in flags else "UNCHANGED")
    source_date=""
    date_basis=""
    for r in group:
        if r["source_date"] and PUBLICATION_BASIS.search(r["date_basis"]):
            source_date,date_basis=r["source_date"],r["date_basis"];break
    verified_recent=False
    try:
        pub=dt.date.fromisoformat(source_date[:10])
        verified_recent=0<=(today-pub).days<=7
    except ValueError:pass
    if verified_recent: freshness="OFFICIAL_PUBLICATION_WITHIN_7_DAYS"
    elif observation=="RECORD_CHANGED":
        freshness="CHANGED_IN_RADAR_PUBLISHER_DATE_NOT_VERIFIED"
    elif observation=="FIRST_OBSERVED":
        freshness="FIRST_OBSERVED_IN_RADAR_NOT_NEW_PUBLICATION"
    else:
        freshness="HISTORICAL_BASELINE_OR_UNCHANGED"
    years_from_apps=[int(r["application_year"]) for r in group
                     if r.get("application_year","").isdigit()]
    years_from_apps.extend(int(m.group(1)) for a in apps
                     if (m:=re.search(r"(?<!\d)(20(?:0\d|1\d|2\d))(?!\d)",a)))
    # Municipal identifiers may use compact years (e.g. 520-11/04).
    # A new 2026 phase at a site with an older file must NOT inherit 2004.
    for app in apps:
        match=re.search(r"(?:/|-)([012]\d)$",app.strip())
        if match:
            inferred=2000+int(match.group(1))
            if 2000<=inferred<=today.year:
                years_from_apps.append(inferred)
    newest=max(years_from_apps) if years_from_apps else 0
    older=bool(newest and newest<today.year-4)
    historical_approval=older and bool(re.search(r"\b(?:approved|noac issued|completed)\b",status,re.I))
    if historical_approval:
        stage_gate="HISTORICAL_APPROVAL_EXCLUDE"
    score=35
    if any(r["source"]=="private_notice" for r in group):score+=18
    if newest>=today.year-1:score+=14
    elif newest>=today.year-2:score+=6
    if re.search(r"\b(?:industrial|warehouse|logistics|manufactur\w*|distribution)\b",scope,re.I):score+=16
    if re.search(r"\b(?:residential|dwelling units|residential units)\b",scope,re.I) and not re.search(r"\bindustrial\b",scope,re.I):score-=12
    if any(_valid(u) and "/dataset/" not in u and "/open-data" not in u
           for u in links):score+=5
    if re.search(r"\b(?:construction|buildings?|[0-9][,.0-9]*\s*(?:m2|m²|sq\.?m|square.metres?))\b",scope,re.I):score+=4
    if observation=="RECORD_CHANGED":score+=3
    if apps:score+=8
    if company:score+=8
    if PRIORITY_SCOPE.search(scope+" "+best["title"]):score+=17
    if stage_gate=="PLANNING_OR_SITE_PLAN_REVIEW":score+=11
    elif stage_gate=="PERMIT_STAGE_VERIFY":score+=5
    elif stage_gate=="PERMIT_OR_NOAC_ISSUED_VERIFY_PROCUREMENT":score-=7
    elif stage_gate=="APPEALED_OR_ON_HOLD":score-=27
    if older:score-=35
    if historical_approval:score-=45
    if freshness=="OFFICIAL_PUBLICATION_WITHIN_7_DAYS":score+=9
    # Project identity uses site and city, NOT application-ID count.
    cid="PRIVATE:"+hashlib.sha256(
        (best["city"].casefold()+"|"+_site(location)).encode()).hexdigest()[:24]
    if re.search(r"industrial|warehouse|logistics|distribution",scope,re.I):
        use="Industrial building; HVAC, sprinklers, electrical, roofing, loading, security"
    elif re.search(r"hotel|mixed.use",scope,re.I):
        use="Mixed-use/hotel; HVAC, fire protection, glazing, electrical, elevators"
    else:
        use="Commercial construction/renovation; scope-dependent contractor or supplier packages"
    next_action=("Identify actual owner/developer and project purchasing contact; "
      "verify application stage, tender/GC status and original publication date")
    result={k:"" for k in FIELDS}
    result.update(opportunity_id=cid,lane="PRIVATE_DEVELOPMENT",
        city=best["city"],address=location,project_name=best["title"] or location,
        nature_of_work=scope,project_stage=status,stage_gate=stage_gate,
        private_ownership_evidence="PRIVATE_SECTOR_LIKELY_OWNER_NOT_VERIFIED",
        company_name=company,company_evidence=company_evidence,
        contact_status="NO_PROJECT_ASSIGNED_CONTACT_VERIFIED",
        application_ids="; ".join(apps),first_seen_local=first_seen,
        observation=observation,source_date=source_date,date_basis=date_basis,
        freshness_class=freshness,source_types="; ".join(source_types),
        source_urls="; ".join(links),commercial_use_cases=use,
        procurement_status="UNKNOWN_NOT_VERIFIED_UNAWARDED",
        score=str(max(0,score)),
        reason=("HISTORICAL_APPLICATION_NOT_SALES_READY" if historical_approval else
                "OLD_APPLICATION_YEAR_REVIEW" if older else
                "PHASE_OR_APPEAL_REVIEW" if stage_gate=="APPEALED_OR_ON_HOLD" else
                "PRIVATE_PROJECT_SOURCE_REVIEW"),
        next_action=next_action)
    return result

def _government(row):
    priority=_str(row.get("priority"))
    if priority not in ("MONITOR_PLANNED","PROJECT_STAGE_REVIEW"):return None
    url=_str(row.get("project_url"))
    if not _valid(url):return None
    title=_str(row.get("project_name"))
    if not title:return None
    # This is ranking by investigation value, NOT procurement availability.
    scope=_str(row.get("scope_of_work"))
    value=_str(row.get("estimated_contract_value"))
    score=35
    if priority=="MONITOR_PLANNED":score+=8
    if _str(row.get("observation")) in ("RECORD_CHANGED","FIRST_OBSERVED"):score+=10
    if "Over $50M" in value:score+=17
    elif "$5M to $50M" in value:score+=9
    elif value:score+=3
    if re.search(r"\b(?:construction|replacement|rehabilitation|bridge|tunnel|facility)\b",scope,re.I):score+=11
    if re.search(r"\b(?:engineering services|appraisal reports|study|assessment)\b",title+" "+scope,re.I):score-=6
    if re.search(r"\b(?:2025|2026|phase\s*2)\b",title+" "+scope,re.I):score+=3
    if _str(row.get("evidence_document_url")):score+=4
    r={k:"" for k in FIELDS}
    r.update(opportunity_id=_str(row.get("record_id")) or
             "GOVERNMENT:"+hashlib.sha256(url.encode()).hexdigest()[:24],
             lane="GOVERNMENT_PROCUREMENT",city=_str(row.get("city")) or
             _str(row.get("authority")),address="",project_name=title,
             nature_of_work=_str(row.get("scope_of_work")),
             project_stage=_str(row.get("stage_hint")),
             stage_gate=priority,company_name=_str(row.get("buyer_organization")),
             company_evidence="PUBLIC_AUTHORITY_SOURCE",
             contact_status="PROCUREMENT_CONTACT_NOT_VERIFIED",
             first_seen_local=_str(row.get("first_seen_local")),
             observation=_str(row.get("observation")),
             source_date=_str(row.get("source_date")),
             date_basis=_str(row.get("source_date_basis")),
             freshness_class="SOURCE_CHANGED_NOT_VERIFIED_NEW_PUBLICATION" if
                _str(row.get("observation")) in ("RECORD_CHANGED","FIRST_OBSERVED")
                else "HISTORICAL_BASELINE_OR_UNCHANGED",
             source_types=_str(row.get("source_type")),source_urls=url,
             estimated_value=_str(row.get("estimated_contract_value")),
             procurement_status="CURRENT_TENDER_AND_AWARD_STATUS_NOT_VERIFIED",
             score=str(score),reason=_str(row.get("rejection_reason")) or
             "PLANNED_PUBLIC_PROCUREMENT_VERIFY_CURRENT_STATUS",
             next_action="Check official procurement portal for current tender, award, package, buyer and eligible bidders")
    return r

def _write(path,records):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
        w.writeheader()
        for row in records:
            w.writerow({k:("'"+str(v) if str(v).startswith(("=","+","-","@")) else v)
                       for k,v in row.items() if k in FIELDS})

def _rank(rows):
    ordered=sorted(rows,key=lambda r:(-int(r["score"]),r["city"],r["project_name"],r["opportunity_id"]))
    for i,r in enumerate(ordered,1):r["rank"]=i
    return ordered

REGION_BY_CITY = {
    "Toronto": "Toronto",
    "Brampton": "Peel", "Mississauga": "Peel", "Caledon": "Peel",
    "Burlington": "Halton", "Oakville": "Halton",
    "Milton": "Halton", "Halton Hills": "Halton",
    "Vaughan": "York", "Markham": "York", "Richmond Hill": "York",
    "Kitchener": "Waterloo", "Waterloo": "Waterloo", "Cambridge": "Waterloo",
    "Ajax": "Durham", "Whitby": "Durham", "Pickering": "Durham",
    "Oshawa": "Durham", "Clarington": "Durham",
    "Guelph": "Wellington", "Hamilton": "Hamilton",
    "Niagara Falls": "Niagara",
}


def _region(city):
    return REGION_BY_CITY.get(city, city)


def _tally(items):
    counts=defaultdict(int)
    for name in items:counts[name]+=1
    return counts


def _balanced_private_top(ordered, *, limit=10):
    """Investigative selection, NOT a change in commercial verification status.

    Fair opportunity to strong records outside Toronto. This is not a quota
    that promotes weak, historical or appealed work when better work exists.
    Caps relax only when the evidence-gated pool is too narrow to fill 10.
    """
    chosen=[]
    selected=set()
    cities=defaultdict(int)
    regions=defaultdict(int)

    def add(row):
        key=row["opportunity_id"]
        if key in selected:return
        chosen.append(dict(row))
        selected.add(key)
        cities[row["city"]]+=1
        regions[_region(row["city"])]+=1

    eligible=[r for r in ordered
              if int(r["score"])>=65
              and r["stage_gate"] not in ("APPEALED_OR_ON_HOLD", "CLOSED_EXCLUDE",
                                          "HISTORICAL_APPROVAL_EXCLUDE")
              and r["source_urls"]]
    # Each credible region's strongest project earns a review slot.
    for row in eligible:
        if len(chosen)>=limit:break
        if not regions[_region(row["city"])]:add(row)
    # Limit dominance by one municipality or region when other good records exist.
    for city_cap,region_cap in ((2,3),(3,4),(limit,limit)):
        for row in eligible:
            if len(chosen)>=limit:break
            if cities[row["city"]]>=city_cap or regions[_region(row["city"])]>=region_cap:
                continue
            add(row)
    # With only one represented region, retain a useful shortlist rather
    # than produce artificial missing slots. Clearly label weaker fallback.
    for row in ordered:
        if len(chosen)>=limit:break
        if row["stage_gate"] not in ("CLOSED_EXCLUDE", "HISTORICAL_APPROVAL_EXCLUDE"):
            add(row)
    return _rank(chosen)


def run(results,*,today=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    today=today or dt.date.today()
    counts={key:0 for key in FILES}
    inputs=[]
    rejected=defaultdict(int)
    for name in ("private_notice","private_master","private_municipal","private_daily","private_qualified"):
        records=_csv(root/FILES[name]);counts[name]=len(records)
        for raw in records:
            obj=_private_item(name,raw)
            if obj:
                if "reject" in obj:rejected[obj["reject"]]+=1
                else:inputs.append(obj)
    # GIS index-only evidence does not generate lead candidates on its own.
    counts["private_gis"]=len(_csv(root/FILES["private_gis"]))
    private=_rank([_candidate(g,today) for g in _group_private(inputs).values()])
    for r in private:
        if r["stage_gate"] in ("CLOSED_EXCLUDE","HISTORICAL_APPROVAL_EXCLUDE"):
            rejected["CLOSED"]+=1
    active=[r for r in private if r["stage_gate"] not in ("CLOSED_EXCLUDE","HISTORICAL_APPROVAL_EXCLUDE")]
    # An observed date or initial baseline is NOT verified publication.
    changed=[r for r in active if r["freshness_class"] in
        ("CHANGED_IN_RADAR_PUBLISHER_DATE_NOT_VERIFIED",
         "FIRST_OBSERVED_IN_RADAR_NOT_NEW_PUBLICATION")]
    confirmed=[r for r in active if r["freshness_class"]=="OFFICIAL_PUBLICATION_WITHIN_7_DAYS"]
    gov_raw=_csv(root/FILES["government"]);counts["government"]=len(gov_raw)
    counts["government_changes"]=len(_csv(root/FILES["government_changes"]))
    counts["government_excluded"]=len(_csv(root/FILES["government_excluded"]))
    govt=_rank([obj for row in gov_raw if (obj:=_government(row))])
    govt_changed=[r for r in govt if r["observation"] in ("RECORD_CHANGED","FIRST_OBSERVED")]
    balanced_top=_balanced_private_top(active,limit=10)
    outputs={PRIVATE_TOP:balanced_top,PRIVATE_ALL:active,PRIVATE_CHANGES:changed,
             PRIVATE_FRESH:confirmed,PRIVATE_REJECTED:[r for r in private if r not in active],
             GOV_TOP:govt[:10],GOV_CHANGES:govt_changed}
    for filename,records in outputs.items():_write(root/filename,records)
    data={"status":"READY","report_date":today.isoformat(),
        "input_rows":counts,"private_projects_eligible":len(active),
        "private_top":len(balanced_top),
        "private_top_city_distribution":dict(sorted(_tally(r["city"] for r in balanced_top).items())),
        "private_top_region_distribution":dict(sorted(_tally(_region(r["city"]) for r in balanced_top).items())),
        "private_selection_rule":"REGION_FIRST_EVIDENCE_FLOOR_WITH_RELAXED_CAPS_WHEN_FEW_CANDIDATES",
        "private_changes_to_verify":len(changed),
        "private_verified_recent_publications":len(confirmed),
        "private_source_rows_discarded":dict(rejected),
        "government_projects_eligible":len(govt),
        "government_top":min(10,len(govt)),
        "government_changes_to_verify":len(govt_changed),
        "government_open_tenders_verified":0,
        "has_first_publication_proof":bool(confirmed),
        "owner_contact_verification":"Source text only; no contacts invented or AI hints promoted",
        "warning":"Private ownership inferred unless named in official project source. A first Radar observation is not a new municipal publication. Public capital programs are NOT verified open tenders.",
        "outputs":list(outputs)+[DASHBOARD]}
    (root/STATUS).write_text(json.dumps(data,indent=2),encoding="utf-8")
    esc=lambda x:html.escape(str(x or ""),quote=True)
    parts=["<!doctype html><html><head><meta charset='utf-8'>",
           "<title>GTA Radar — Private and Public Opportunities</title>",
           "<style>body{font:15px Segoe UI,Arial;max-width:1100px;margin:32px auto;padding:0 16px;color:#24313c}"
           "table{border-collapse:collapse;width:100%}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left}"
           "th{background:#f2f5f7}small{color:#596977}a{color:#065a91}</style></head><body>",
           "<h1>GTA Radar — Private vs Government Intelligence</h1>",
           "<p>Separate rankings. Private ownership and purchasing contacts require verification. "
           "No procurement or publication claims are inferred from first observation.</p>"]
    for title,filename,rows in [
        ("Private development — region-balanced investigation shortlist",PRIVATE_TOP,balanced_top),
        ("Government procurement — planned and stage-to-verify",GOV_TOP,govt[:10])]:
        parts.extend(["<h2>"+esc(title)+"</h2>",
            "<p><a href='"+esc(filename)+"'>Open full CSV</a></p>",
            "<table><thead><tr><th>#</th><th>City</th><th>Project / work</th>"
            "<th>Stage</th><th>Company/owner evidence</th><th>Source</th></tr></thead><tbody>"])
        for row in rows:
            link=next(iter(_links(row.get("source_urls"))),"")
            source="<a href='"+esc(link)+"' rel='noopener noreferrer'>Official source</a>" if link else "Not linked"
            parts.append("<tr><td>"+esc(row["rank"])+"</td><td>"+esc(row["city"])+
                "</td><td><b>"+esc(row["project_name"])+"</b><br><small>"+
                esc(row["nature_of_work"][:220])+"</small></td><td>"+
                esc(row["stage_gate"])+"</td><td>"+esc(row["company_name"] or
                    row["private_ownership_evidence"] or row["contact_status"])+
                "</td><td>"+source+"</td></tr>")
        parts.append("</tbody></table>")
    parts.append("<p><a href='"+PRIVATE_CHANGES+"'>Private changes to verify</a> · "+
                 "<a href='"+PRIVATE_FRESH+"'>Verified recent private publications</a> · "+
                 "<a href='"+GOV_CHANGES+"'>Government project changes</a> · "+
                 "<a href='"+STATUS+"'>Coverage and evidence diagnostics</a></p></body></html>")
    (root/DASHBOARD).write_text("".join(parts),encoding="utf-8")
    return data


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(
        description="Rebuild private and government top-10 rankings from existing Radar results; no network collection.")
    parser.add_argument("--results",required=True,help="Existing GTA_RADAR_RESULTS folder")
    args=parser.parse_args()
    print(json.dumps(run(args.results),indent=2))
