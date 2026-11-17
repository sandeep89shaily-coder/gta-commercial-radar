"""Three source-specific Southern Ontario expansion pilots — evidence, not sales leads.

Niagara Falls: enrich already-collected GGH application IDs via official
same-host /Planning/Details/<number> pages.
Brantford: inspect city-owned planning + building permit ArcGIS FeatureServer
layers; validate the published schema; paginate bounded records.
St. Catharines: collect project-specific dated notices from the City's public
notice list. Filing/complete, posted, meeting and permit issue dates remain
distinct and NEVER prove first project disclosure or unawarded procurement.

All transport uses public DNS checks, robots policy, HTTPS allowlists, TLS
verification, no redirects, response limits. A blocked/inaccessible source is
reported as blocked, not silently replaced with old data. No paid calls.
Initial baseline is never a new event or lead.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import socket
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from gta_ggh_early_planning import _fetch as fetch_html_official
from robots_policy import evaluate
from toronto_pdf_download import public_dns

NIAGARA_INDEX = "GTA_RADAR_GGH_EXPANSION_APPLICATIONS.csv"
NIAGARA_BASE = "https://webpublic.niagarafalls.ca/Planning/"
STC_INDEX = "https://www.stcatharines.ca/news/public-notices/?page=1"
BRANTFORD = {
    "PLANNING": "https://services.arcgis.com/aji2lCmjXt0KpGzI/ArcGIS/rest/services/Planning_Application_Open_Data_view/FeatureServer/0",
    "BUILDING_PERMIT": "https://services.arcgis.com/aji2lCmjXt0KpGzI/ArcGIS/rest/services/City_of_Brantford_Building_Permits_view/FeatureServer/0",
}
OUTPUT = "GTA_RADAR_THREE_CITY_EVIDENCE_CANDIDATES.csv"
CHANGES = "GTA_RADAR_THREE_CITY_EVIDENCE_CHANGED.csv"
STATUS = "GTA_RADAR_THREE_CITY_EVIDENCE_STATUS.json"
LEDGER = "GTA_RADAR_THREE_CITY_EVIDENCE_SEEN.json"
FIELDS = (
    "candidate_key", "city", "source_lane", "record_kind", "application_id",
    "address", "scope", "application_status", "applicant_name_source_claim",
    "planner_name", "planner_email_public", "contact_role",
    "source_date", "source_date_basis", "notice_posted_date",
    "notice_date_basis", "application_complete_date", "meeting_date",
    "source_url", "documents_listed", "source_document_count",
    "first_seen_local", "observation", "change_basis",
    "supplier_buyer_verified", "first_project_publication_verified",
    "open_procurement_verified", "verification_required",
)
AGENT = "GTARadarThreeCitySourceEvidence/1.0"
MAX_NIAGARA = 18
MAX_STC_NOTICES = 14
MAX_GIS_PER_LAYER = 200
MAX_BYTES = 2_500_000
ID_NIAGARA = re.compile(r"\b(?:AM-\d{4}-\d{3}|(?:26T|26CD)-\d{2}-\d{4}-\d{3}|(?:A|B|SBA)-\d{4}-\d{3})\b", re.I)
FILE_STC = re.compile(r"\b\d{2}\s+\d{6}\s+(?:OP|ZA|SP|SC|CO|SV)\b", re.I)
ADDRESS = re.compile(r"\b\d{1,5}\s+[A-Za-z0-9][A-Za-z0-9 .,'&/-]{2,90}\b", re.I)
DATE_TEXT = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2}"
PUB_SHORT = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+20\d{2}\b", re.I)
PUB_LONG = re.compile(r"\b" + DATE_TEXT + r"\b", re.I)
PERSON = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*,\s*(?:(?:Senior|Principal|City|Development)\s+)?Planner\b", re.I)
CITY_EMAIL = re.compile(r"\b[A-Z0-9_.+-]+@stcatharines\.ca\b", re.I)
NIAGARA_EMAIL = re.compile(r"\b[A-Z0-9_.+-]+@niagarafalls\.ca\b", re.I)
COMMERCIAL = re.compile(r"\b(?:industrial|manufactur\w*|factory|warehouse|logistics|distribution|"
                        r"commercial|retail|hotel|mixed[- ]use|data cent(?:re|er)|"
                        r"restaurant|office|medical|institutional|annex|employment)\b", re.I)
FIELDS_PLANNING = {
    "identity": ("ApplicationNum", "APPLICATIONNUM", "ApplicationNumber"),
    "address": ("Address", "ADDRESS"),
    "description": ("Description", "DESCRIPTION", "Proposed_use"),
    "date": ("Submitted_date", "SubmittedDate"),
    "status": ("Status", "STATUS"),
    "applicant": ("Applicant", "APPLICANT"),
    "planner": ("Planner_assigned", "PlannerAssigned"),
    "email": ("Planner_email", "PlannerEmail"),
}
FIELDS_PERMIT = {
    "identity": ("PermitNumber", "PermitNum", "PERMITNUMBER", "Permit_Number", "PermitNo"),
    "address": ("Address", "ADDRESS", "SiteAddress", "FullAddress"),
    "description": ("WorkType", "Work_Type", "Work_Description", "Description", "PermitType"),
    "date": ("IssueDate", "Issued_date", "IssuedDate", "ISSUEDATE"),
    "status": ("Status", "PermitStatus", "PERMITSTATUS"),
    "applicant": ("Applicant", "APPLICANT"),
    "planner": (),
    "email": (),
}


def _clean(value):
    return " ".join(str(value or "").split())


def _date(value):
    if value in (None, "", 0):
        return ""
    if isinstance(value, (int, float)):
        try:
            # ArcGIS esriFieldTypeDate commonly uses Unix milliseconds.
            return dt.datetime.fromtimestamp(value / 1000, tz=dt.timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            return ""
    raw = _clean(value)
    try:
        return dt.date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        pass
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _safe(url, host, prefix):
    try:
        p = urlsplit(str(url or ""))
        return (p.scheme == "https" and p.hostname == host and
                p.port in (None, 443) and not p.username and not p.password
                and not p.fragment and p.path.startswith(prefix) and
                not p.query)
    except ValueError:
        return False


def _key(city, lane, ident):
    return "PILOT3:" + hashlib.sha256(
        (city + "|" + lane + "|" + _clean(ident).upper()).encode("utf-8")
    ).hexdigest()[:24]


def _read(path):
    if not path.is_file():
        return []
    if path.is_symlink() or path.stat().st_size > 8_000_000:
        raise ValueError("UNSAFE_INPUT_FILE")
    with path.open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def _save(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            vals = {}
            for key in FIELDS:
                value = str(row.get(key, "") if row.get(key) is not None else "")
                vals[key] = "'" + value if value.lstrip().startswith(
                    ("=", "+", "-", "@", "\t", "\r")) else value
            writer.writerow(vals)


def _new(city, lane, ident, url, **values):
    result = {key: "" for key in FIELDS}
    result.update({
        "candidate_key": _key(city, lane, ident),
        "city": city, "source_lane": lane,
        "record_kind": "OFFICIAL_PERMIT" if lane == "BRANTFORD_BUILDING_PERMIT"
                       else "OFFICIAL_APPLICATION_OR_NOTICE_REVIEW",
        "application_id": _clean(ident),
        "source_url": url,
        "supplier_buyer_verified": "False",
        "first_project_publication_verified": "False",
        "open_procurement_verified": "False",
        "verification_required": "Verify original project announcement, legal project organization, "
                                 "current stage, procurement package and real purchasing authority.",
    })
    result.update({k: _clean(v) for k, v in values.items() if k in FIELDS})
    return result


def parse_niagara(markup, source_row):
    """Extract a specific detail record only when its heading carries exact file ID."""
    url = source_row.get("official_record_url", "")
    if not _safe(url, "webpublic.niagarafalls.ca", "/Planning/Details/") or not re.fullmatch(
            r"/Planning/Details/\d+/?", urlsplit(url).path):
        raise ValueError("INVALID_NIAGARA_DETAIL_LINK")
    soup = BeautifulSoup(markup, "html.parser")
    main = soup.find("main") or soup
    header = next((h for h in main.find_all(["h1", "h2", "h3"])
                   if ID_NIAGARA.search(_clean(h.get_text(" ", strip=True)))), None)
    if not header:
        raise ValueError("NIAGARA_APPLICATION_HEADING_MISSING")
    heading = _clean(header.get_text(" ", strip=True))
    ident = _clean(source_row.get("application_id"))
    if re.sub(r"[^A-Z0-9]", "", ident.upper()) not in re.sub(
            r"[^A-Z0-9]", "", heading.upper()):
        raise ValueError("NIAGARA_DETAIL_ID_NOT_MATCHED")
    paragraphs = []
    for node in header.find_all_next(["p", "h3", "h2"], limit=24):
        if node.name in ("h3", "h2"):
            break
        value = _clean(node.get_text(" ", strip=True))
        if value and value not in paragraphs:
            paragraphs.append(value)
        if sum(map(len, paragraphs)) > 1600:
            break
    scope = " ".join(paragraphs)[:1100]
    if not scope:
        # Some municipal pages put the proposal in a plain div, not p.
        text = _clean(main.get_text(" ", strip=True))
        at = text.find(heading)
        scope = text[at + len(heading): at + len(heading) + 800]
        scope = re.split(r"\bMeeting Date\b|\bApplication Types\b", scope)[0]
    contact = next((h for h in main.find_all(["h2", "h3", "h4"])
                    if _clean(h.get_text(" ", strip=True)).lower() == "contact"), None)
    ctext = ""
    if contact:
        siblings = []
        for node in contact.find_all_next(["p", "a", "h2", "h3", "h4"], limit=14):
            if node.name in ("h2", "h3", "h4"):
                break
            siblings.append(_clean(node.get_text(" ", strip=True)))
        ctext = " ".join(siblings)
    bodytext = _clean(main.get_text(" ", strip=True))
    planner = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-zA-Z]+){1,2})\s+Planner\s*\d", ctext or bodytext)
    email = NIAGARA_EMAIL.search(ctext)
    docsection = next((h for h in main.find_all(["h2", "h3", "h4"])
                       if "associated files" in _clean(h.get_text(" ", strip=True)).lower()), None)
    docs = []
    if docsection:
        for node in docsection.find_all_next(["a", "h2", "h3", "h4"], limit=95):
            if node.name in ("h2", "h3", "h4"):
                break
            name = _clean(node.get_text(" ", strip=True))
            href = urljoin(url, str(node.get("href") or ""))
            if name and _safe(href, "webpublic.niagarafalls.ca", "/Files/Planning/Applications/"):
                docs.append(name[:90])
    meeting = re.search(r"\bMeeting Date\s+(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+)?(" + DATE_TEXT + r")", bodytext, re.I)
    return _new("Niagara Falls", "NIAGARA_APPLICATION_DETAIL", ident, url,
        address=source_row.get("address") or heading.split("(")[0],
        scope=scope, applicant_name_source_claim="",
        application_status="PLANNING_APPLICATION_MEETING",
        meeting_date=_date(meeting.group(1)) if meeting else "",
        planner_name=planner.group(1) if planner else "",
        planner_email_public=email.group() if email else "",
        contact_role="CITY_PLANNER_NOT_PURCHASING_AUTHORITY" if contact else "",
        documents_listed=" | ".join(docs[:20]), source_document_count=len(docs),
        source_date="", source_date_basis="MEETING_DATE_NOT_FILING_OR_FIRST_PUBLICATION",
        notice_date_basis="ORIGINAL_PROJECT_PUBLICATION_UNKNOWN")


def parse_stc(markup, url, *, today=None):
    """Extract notice posting date separately from application completion date."""
    if not _safe(url, "www.stcatharines.ca", "/news/posts/"):
        raise ValueError("INVALID_STC_NOTICE_URL")
    soup = BeautifulSoup(markup, "html.parser")
    main = soup.find("main") or soup
    heading = main.find("h1")
    if heading is None:
        raise ValueError("STC_NOTICE_TITLE_MISSING")
    title = _clean(heading.get_text(" ", strip=True))
    if not re.search(r"\b(?:planning|applications?|zoning|official plan|development|site plan)\b",
                     title, re.I):
        raise ValueError("NON_PLANNING_NOTICE")
    content = _clean(main.get_text(" ", strip=True))
    if not re.search(r"\b(?:proposal|applications? (?:to|for)|amend)\b", content, re.I):
        raise ValueError("NOTICE_HAS_NO_APPLICATION_PROPOSAL")
    htext = _clean(heading.find_next(string=True) or "")
    # Publication metadata must be adjacent to the notice title, not a
    # historical application date deep inside the proposal. Never use a
    # generic first date on the page as posting evidence.
    near = content[content.find(title) + len(title):][:75] if title in content else ""
    dates = re.match(r"^\s*(?:-\s*)?(" + PUB_SHORT.pattern + "|" + PUB_LONG.pattern + r")", near, re.I)
    posted = _date(dates.group(1)) if dates else ""
    if posted and today and posted > today.isoformat():
        raise ValueError("FUTURE_NOTICE_POSTING")
    complete = re.search(r"\bdeclared complete as of\s+(" + DATE_TEXT + r")", content, re.I)
    complete_date = _date(complete.group(1)) if complete else ""
    start = re.search(r"\bPROPOSAL\b", content, re.I)
    end = re.search(r"\bMORE INFORMATION\b|\bHOW TO PARTICIPATE\b|\bTO PARTICIPATE\b", 
                    content[start.end():] if start else "", re.I)
    scope = content[start.end():][:end.start() if end else 1300] if start else content[:1100]
    ids = FILE_STC.findall(content)
    if not ids:
        # Preserve a project-page notice as a notice, not a fictional file ID.
        ident = url
        kind = "OFFICIAL_NOTICE_NO_EXACT_FILE_ID"
    else:
        ident = "|".join(sorted(set(_clean(x).upper() for x in ids)))
        kind = "OFFICIAL_APPLICATION_NOTICE"
    email = CITY_EMAIL.search(content)
    person = PERSON.search(content)
    addr = re.search(r"\blands located at\s+([^.]{7,95})", content, re.I)
    result = _new("St. Catharines", "STC_PLANNING_NOTICE", ident, url,
        address=_clean(addr.group(1)) if addr else title.split(" - ")[-1][:110],
        scope=scope[:1250], planner_name=re.sub(r"^(?:Contact|Email|Please)\s+",
                    "", person.group(1)) if person else "",
        planner_email_public=email.group() if email else "",
        contact_role="MUNICIPAL_PLANNER_NOT_PROJECT_BUYER" if email else "",
        notice_posted_date=posted,
        notice_date_basis="OFFICIAL_NOTICE_PAGE_DATE_NOT_FIRST_PROJECT_DISCLOSURE"
                          if posted else "NO_NOTICE_PAGE_DATE",
        application_complete_date=complete_date,
        source_date=complete_date,
        source_date_basis="APPLICATION_COMPLETE_DATE_NOT_FIRST_PUBLICATION"
                          if complete_date else "FILING_DATE_UNKNOWN",
        application_status="PUBLIC_PLANNING_NOTICE")
    result["record_kind"] = kind
    return result


def _niagara_sources(root):
    rows = [r for r in _read(root / NIAGARA_INDEX) if
            r.get("city") == "Niagara Falls"
            and ID_NIAGARA.search(_clean(r.get("application_id")))]
    # Source URLs are exact record links from the already-run official GGH
    # collector. Concentrate on recent-numbered, commercially useful files.
    rows.sort(key=lambda r: (
        int(bool(COMMERCIAL.search(_clean(r.get("description"))))),
        int(bool(re.search(r"\b2026\b", _clean(r.get("application_id"))))),
        _clean(r.get("application_id"))), reverse=True)
    unique = {}
    for row in rows:
        url = str(row.get("official_record_url") or "")
        if _safe(url, "webpublic.niagarafalls.ca", "/Planning/Details/") and re.fullmatch(
                r"/Planning/Details/\d+/?", urlsplit(url).path):
            unique.setdefault(row["project_id"], row)
    return list(unique.values())[:MAX_NIAGARA]


def _stc_links(markup):
    soup = BeautifulSoup(markup, "html.parser")
    main = soup.find("main") or soup
    links = []
    seen = set()
    for a in main.find_all("a", href=True):
        title = _clean(a.get_text(" ", strip=True))
        url = urljoin(STC_INDEX, a["href"])
        if (not _safe(url, "www.stcatharines.ca", "/news/posts/")
                or not re.search(r"\b(?:applications?|planning|zoning|development|site.plan)\b",
                                 title + " " + urlsplit(url).path.replace("-", " "), re.I)
                or url in seen):
            continue
        seen.add(url)
        links.append(url)
        if len(links) >= MAX_STC_NOTICES:
            break
    return links


def _fetch_arcgis(url, params, *, session_factory=requests.Session):
    if url not in BRANTFORD.values():
        raise ValueError("UNALLOWLISTED_BRANTFORD_LAYER")
    host = urlsplit(url).hostname
    if not public_dns(host, socket.getaddrinfo):
        raise ValueError("PUBLIC_DNS_NOT_AVAILABLE")
    with session_factory() as session:
        session.trust_env = False
        session.headers.update({"User-Agent": AGENT, "Accept": "application/json"})
        request = requests.Request("GET", url, params=params).prepare()
        allowed, reason = evaluate(session, request.url, AGENT, timeout=8)
        if not allowed:
            raise ValueError("ROBOTS_DENIED:" + str(reason))
        with session.get(request.url, timeout=(6,18), allow_redirects=False, stream=True) as response:
            if response.status_code != 200 or response.url != request.url:
                raise ValueError("ARCGIS_HTTP_" + str(response.status_code) + "_OR_REDIRECT")
            raw = bytearray()
            for part in response.iter_content(65536):
                raw.extend(part)
                if len(raw) > MAX_BYTES:
                    raise ValueError("ARCGIS_RESPONSE_TOO_LARGE")
        doc = json.loads(raw)
        if not isinstance(doc, dict) or doc.get("error"):
            raise ValueError("ARCGIS_ERROR_OR_NON_OBJECT")
        return doc


def _field_name(fields, choices):
    available = {str(x).casefold(): x for x in fields}
    return next((available[x.casefold()] for x in choices if x.casefold() in available), None)


def _gis_date(value, day):
    got = _date(value)
    if got and got > day.isoformat():
        return "", "FUTURE_SOURCE_DATE_HELD"
    return got, ""


def _fetch_brantford(layer, *, json_fetch=None, today=None):
    """Validate schema then query limited pages. Any incomplete result is held."""
    day = today or dt.date.today()
    base = BRANTFORD[layer]
    getter = json_fetch or _fetch_arcgis
    meta = getter(base, {"f":"json"})
    fields = {x.get("name"): x.get("type", "") for x in meta.get("fields", [])
              if isinstance(x, dict) and x.get("name")}
    if not fields:
        raise ValueError("BRANTFORD_METADATA_SCHEMA_MISSING")
    roles = FIELDS_PLANNING if layer == "PLANNING" else FIELDS_PERMIT
    names = {role: _field_name(fields, choices) for role, choices in roles.items()}
    if not names["identity"]:
        raise ValueError("BRANTFORD_PUBLIC_IDENTIFIER_FIELD_MISSING")
    oid = str(meta.get("objectIdField") or _field_name(fields, ("OBJECTID", "ObjectId")) or "")
    if not oid:
        raise ValueError("BRANTFORD_OID_PAGINATION_MISSING")
    gathered = []
    limit = 100
    for offset in (0, 100):
        query = {
            "f":"json", "where":"1=1", "outFields":"*",
            "returnGeometry":"false", "orderByFields":oid + " DESC",
            "resultOffset":str(offset), "resultRecordCount":str(limit),
        }
        response = getter(base, query)
        features = response.get("features")
        if not isinstance(features, list):
            raise ValueError("BRANTFORD_ARCGIS_FEATURES_MISSING")
        gathered.extend(features)
        if len(features) < limit and not response.get("exceededTransferLimit"):
            break
    if len(gathered) >= MAX_GIS_PER_LAYER and response.get("exceededTransferLimit"):
        raise ValueError("BRANTFORD_PAGINATION_TRUNCATED_REQUIRES_CONTINUATION")
    results = []
    ids = set()
    for item in gathered:
        if not isinstance(item, dict) or not isinstance(item.get("attributes"), dict):
            raise ValueError("BRANTFORD_INVALID_FEATURE")
        attrs = item["attributes"]
        def at(key):
            return attrs.get(names[key]) if names.get(key) else None
        ident = _clean(at("identity"))
        if not ident or len(ident) > 120:
            continue
        key = _key("Brantford", "BRANTFORD_" + layer, ident)
        if key in ids:
            raise ValueError("DUPLICATE_BRANTFORD_OFFICIAL_FILE_NUMBER")
        ids.add(key)
        raw_date, rejected = _gis_date(at("date"), day)
        if rejected:
            raise ValueError(rejected)
        results.append(_new("Brantford", "BRANTFORD_" + layer, ident, base,
            address=_clean(at("address"))[:180], scope=_clean(at("description"))[:1100],
            application_status=_clean(at("status"))[:120],
            applicant_name_source_claim=_clean(at("applicant"))[:180],
            planner_name=_clean(at("planner"))[:120],
            planner_email_public=_clean(at("email"))[:200],
            contact_role="CITY_PLANNER_NOT_BUYER" if at("email") else "",
            source_date=raw_date,
            source_date_basis=("CITY_PLANNING_SUBMITTED_DATE_NOT_PUBLICATION"
               if layer == "PLANNING" else "CITY_PERMIT_ISSUE_DATE_NOT_PUBLICATION")
               if raw_date else "SOURCE_DATE_NOT_AVAILABLE",
            notice_date_basis="NO_VERIFIED_FIRST_PROJECT_ANNOUNCEMENT"))
    return results, {"metadata_fields":len(fields), "rows_returned":len(gathered),
                     "records_with_ids":len(results), "query_limit":MAX_GIS_PER_LAYER,
                     "query_endpoint":base,
                     "records_represent_entire_layer":len(gathered)<MAX_GIS_PER_LAYER,
                     "publisher_publication_date_verified":False}


def run(results, *, today=None, html_fetch=None, json_fetch=None,
        niagara_limit=MAX_NIAGARA, stc_limit=MAX_STC_NOTICES):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_GTA_RADAR_RESULTS_REQUIRED")
    day = today or dt.date.today()
    fetch = html_fetch or fetch_html_official
    statefile = root / LEDGER
    state = json.loads(statefile.read_text(encoding="utf-8")) if statefile.is_file() else {}
    if not isinstance(state, dict) or state.get("schema", 1) != 1:
        raise ValueError("INVALID_PILOT_HISTORY")
    previous = state.get("records", {})
    if not isinstance(previous, dict):
        raise ValueError("INVALID_PILOT_HISTORY_RECORDS")
    history = dict(previous)
    accepted, changed, sources = [], [], []

    def incorporate(row):
        key = row["candidate_key"]
        digest = hashlib.sha256(json.dumps({x:row[x] for x in FIELDS
            if x not in ("first_seen_local", "observation", "change_basis")},
            sort_keys=True).encode("utf-8")).hexdigest()
        prior = previous.get(key)
        change = ("INITIAL_BASELINE_NOT_NEW_PUBLICATION" if not prior else
                  "UNCHANGED" if prior.get("digest") == digest else
                  "SOURCE_CHANGED_NOT_VERIFIED_NEW_PROJECT")
        row["first_seen_local"] = (prior or {}).get("first_seen_local", day.isoformat())
        row["observation"] = change
        row["change_basis"] = ("OFFICIAL_SOURCE_CONTENT_FINGERPRINT_CHANGED"
                               if change.startswith("SOURCE_CHANGED") else "")
        accepted.append(row)
        if change.startswith("SOURCE_CHANGED"):
            changed.append(row)
        history[key] = {
            "digest":digest, "first_seen_local":row["first_seen_local"],
            "last_seen_local":day.isoformat(), "source_url":row["source_url"]}
    niagara = _niagara_sources(root)[:max(0, min(int(niagara_limit), MAX_NIAGARA))]
    stage = {"city":"Niagara Falls", "source_lane":"NIAGARA_APPLICATION_DETAIL",
             "eligible_saved_application_links":len(niagara),"fetched":0,"failures":[]}
    for original in niagara:
        url = original["official_record_url"]
        try:
            candidate = parse_niagara(fetch(url), original)
            incorporate(candidate)
            stage["fetched"] += 1
        except Exception as exc:
            stage["failures"].append({"url":url,"reason":type(exc).__name__+":"+str(exc)[:140]})
    stage["status"] = "PARTIAL_OR_HELD" if stage["failures"] else (
        "DETAILS_CAPTURED_REVIEW_ONLY" if stage["fetched"] else "NO_VALID_SAVED_DETAIL_LINKS")
    sources.append(stage)
    stc = {"city":"St. Catharines", "source_lane":"STC_PLANNING_NOTICE",
           "index":STC_INDEX,"found_links":0,"fetched":0,"failures":[]}
    try:
        links = _stc_links(fetch(STC_INDEX))[:max(0, min(int(stc_limit), MAX_STC_NOTICES))]
        stc["found_links"] = len(links)
        for url in links:
            try:
                record = parse_stc(fetch(url), url, today=day)
                incorporate(record)
                stc["fetched"] += 1
            except Exception as exc:
                stc["failures"].append({"url":url,"reason":type(exc).__name__+":"+str(exc)[:140]})
    except Exception as exc:
        stc["failures"].append({"url":STC_INDEX,"reason":type(exc).__name__+":"+str(exc)[:140]})
    stc["status"] = "PARTIAL_OR_HELD" if stc["failures"] else (
        "DATED_NOTICE_REVIEW_ONLY" if stc["fetched"] else "NO_PLANNING_NOTICES_EXTRACTED")
    sources.append(stc)
    for layer in BRANTFORD:
        audit = {"city":"Brantford", "source_lane":"BRANTFORD_" + layer,
                 "official_layer":BRANTFORD[layer], "fetched":0, "failures":[]}
        try:
            records, details = _fetch_brantford(layer, json_fetch=json_fetch, today=day)
            for record in records:
                incorporate(record)
            audit.update(details)
            audit["fetched"] = len(records)
            audit["status"] = "OFFICIAL_LAYER_RECORDS_REVIEW_ONLY"
        except Exception as exc:
            audit["status"] = "SOURCE_BLOCKED_OR_UNSUPPORTED"
            audit["failures"].append(type(exc).__name__+":"+str(exc)[:180])
        sources.append(audit)
    _save(root / OUTPUT, accepted)
    _save(root / CHANGES, changed)
    if history != previous:
        temp = statefile.with_suffix(".tmp")
        temp.write_text(json.dumps({"schema":1,"records":history},indent=2),encoding="utf-8")
        temp.replace(statefile)
    report = {
        "status":"EXPERIMENTAL_THREE_CITY_SOURCE_EVIDENCE_NOT_CUSTOMER_READY",
        "as_of":day.isoformat(), "candidate_rows":len(accepted),
        "changed_source_rows_not_new_project_proof":len(changed),
        "original_publisher_first_disclosures_verified":0,
        "verified_project_buyers":0, "verified_open_supplier_packages":0,
        "municipalities_added_to_verified_16_city_count":0,
        "sources":sources,"network_calls_estimate_not_audit":None,
        "paid_ai_calls":0,
        "warning":"Source page notice/meeting dates, GIS submission dates and permit "
                  "issue dates are distinct from original construction announcement dates. "
                  "Source failures are recorded and first collection is baseline only.",
        "outputs":[OUTPUT, CHANGES, STATUS],
    }
    (root / STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True)
    args = p.parse_args()
    print(json.dumps(run(args.results),indent=2))


if __name__ == "__main__":
    main()
