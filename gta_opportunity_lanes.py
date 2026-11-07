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
            company_evidence="NAMED_ON_THIS_OFFICIAL_PROJECT_PAGE_VERIFY_ROLE"
    if not company and source=="private_municipal":
        match=re.search(r"\b(?:application (?:made|submitted) by|applicant[: ])\s*"
                        r"([A-Z][\w .&,'()-]{5,110}?)(?=\s*(?:for |to |at |\.|;|$))",
                        description,re.I)
        if match and COMPANY_END.search(match.group(1)):
            company=_str(match.group(1))[:180]
            company_evidence="SOURCE_TEXT_EXPLICIT_APPLICANT_VERIFY_ROLE"
    private_evidence=("EXPLICIT_COMPANY_NAMED_IN_PROJECT" if company
                      else "PRIVATE_USE_INFERRED_OWNER_UNVERIFIED")
    return dict(city=city,address=address,title=title,description=description,
        status=status,application_id=ident,urls=urls,source=source,
        observation=observation,first_seen=firstseen,source_date=date,date_basis=basis,
        company=company,company_evidence=company_evidence,
        private_evidence=private_evidence,kind=kind)

def _group_private(rows):
    # One project, possibly multiple OPA/ZBA/Site Plan file numbers.
    # Site-specific grouping only, never 2 distinct streets or all city files.
    grouped=defaultdict(list)
    for r in rows:
        if "reject" in r:continue
        site=_site(r["address"]) or _site(_site_from_title(r["title"]))
        # If no address, a specific official detail URL is a safe fallback.
        if site:
            key=(r["city"].casefold(),site)
        else:
            url=r["urls"][0] if r["urls"] else ""
            key=(r["city"].casefold(),"URL:"+url)
        grouped[key].append(r)
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
    years_from_apps=[int(m.group(1)) for a in apps
                     if (m:=re.search(r"(?<!\d)(20(?:0\d|1\d|2\d))(?!\d)",a))]
    older=bool(years_from_apps and min(years_from_apps)<today.year-4)
    score=35
    if any(r["source"]=="private_notice" for r in group):score+=18
    if apps:score+=8
    if company:score+=13
    if PRIORITY_SCOPE.search(scope+" "+best["title"]):score+=17
    if stage_gate=="PLANNING_OR_SITE_PLAN_REVIEW":score+=11
    elif stage_gate=="PERMIT_STAGE_VERIFY":score+=5
    elif stage_gate=="PERMIT_OR_NOAC_ISSUED_VERIFY_PROCUREMENT":score-=7
    elif stage_gate=="APPEALED_OR_ON_HOLD":score-=27
    if older:score-=22
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
        private_ownership_evidence="EXPLICIT_COMPANY_NAMED_IN_PROJECT" if company else
            "PRIVATE_SECTOR_LIKELY_OWNER_NOT_VERIFIED",
        company_name=company,company_evidence=company_evidence,
        contact_status="NO_PROJECT_ASSIGNED_CONTACT_VERIFIED",
        application_ids="; ".join(apps),first_seen_local=first_seen,
        observation=observation,source_date=source_date,date_basis=date_basis,
        freshness_class=freshness,source_types="; ".join(source_types),
        source_urls="; ".join(links),commercial_use_cases=use,
        procurement_status="UNKNOWN_NOT_VERIFIED_UNAWARDED",
        score=str(max(0,score)),
        reason=("OLD_APPLICATION_YEAR_REVIEW" if older else
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
    score=40
    if priority=="MONITOR_PLANNED":score+=15
    if _str(row.get("observation")) in ("RECORD_CHANGED","FIRST_OBSERVED"):score+=8
    if _str(row.get("estimated_contract_value")):score+=7
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

def run(results,*,today=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    today=today or dt.date.today()
    counts={key:0 for key in FILES}
    inputs=[]
    rejected=defaultdict(int)
    for name in ("private_notice","private_master","private_municipal","private_daily"):
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
        if r["stage_gate"]=="CLOSED_EXCLUDE":
            rejected["CLOSED"]+=1
    active=[r for r in private if r["stage_gate"]!="CLOSED_EXCLUDE"]
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
    outputs={PRIVATE_TOP:active[:10],PRIVATE_ALL:active,PRIVATE_CHANGES:changed,
             PRIVATE_FRESH:confirmed,PRIVATE_REJECTED:[r for r in private if r not in active],
             GOV_TOP:govt[:10],GOV_CHANGES:govt_changed}
    for filename,records in outputs.items():_write(root/filename,records)
    data={"status":"READY","report_date":today.isoformat(),
        "input_rows":counts,"private_projects_eligible":len(active),
        "private_top":min(10,len(active)),
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
        ("Private development — top opportunities",PRIVATE_TOP,active[:10]),
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
