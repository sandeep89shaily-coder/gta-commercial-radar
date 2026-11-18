"""Northern major-city official-source Radar pilot: Barrie, Greater Sudbury, North Bay.

Experimental source evidence only. Does not change original 16-city coverage,
legacy GGH Barrie baseline, paid AI, buyer verification, or sales release.
Date received / status / notice dates are NOT first project publication.
Network transport respects publisher robots, DNS, exact official hosts,
TLS, no redirects, byte caps, and bounded page counts.
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
from gta_ggh_early_planning import _fetch as official_html
from robots_policy import evaluate
from toronto_pdf_download import public_dns

BARRIE = {
    "PLANNING": "https://gispublic.barrie.ca/arcgis/rest/services/Open_Data/Planning/MapServer/4",
    "ACTIVE_PERMITS": "https://gispublic.barrie.ca/arcgis/rest/services/Open_Data/APLI/MapServer/0",
    "ISSUED_PERMITS": "https://gispublic.barrie.ca/arcgis/rest/services/Open_Data/APLI/MapServer/1",
}
SUDBURY = ("https://www.greatersudbury.ca/do-business/planning-and-development/"
           "pending-planning-applications/")
SUDBURY_DOC_INDEX = SUDBURY + "upcoming-docs/"
SUDBURY_DOC_LINKS = "GTA_RADAR_SUDBURY_OFFICIAL_NOTICE_DOCUMENT_LINKS.csv"
NORTH_BAY = "https://northbay.ca/city-government/media-room/public-notices/"
SOURCE_FILE = "GTA_RADAR_NORTHERN_MAJOR_CITY_EVIDENCE.csv"
CHANGED_FILE = "GTA_RADAR_NORTHERN_MAJOR_CITY_SOURCE_CHANGES.csv"
STATUS_FILE = "GTA_RADAR_NORTHERN_MAJOR_CITY_STATUS.json"
LEDGER_FILE = "GTA_RADAR_NORTHERN_MAJOR_CITY_LEDGER.json"
AGENT = "GTARadarNorthernCityEvidence/1.0"
MAX_BYTES = 3_500_000
PAGE_SIZE = 450
MAX_BARRIE_PAGES = {"PLANNING": 4, "ACTIVE_PERMITS": 8, "ISSUED_PERMITS": 16}
MAX_NB_PAGES = 3
MAX_NB_DETAILS = 12
FIELDS = (
    "candidate_id", "city", "source_lane", "record_kind", "application_id",
    "project_title", "address", "scope", "current_status",
    "applicant_name_source_claim", "planning_contact_name", "planning_contact_email",
    "source_date", "source_date_basis", "publication_date_verified",
    "commercial_scope_text_match", "original_record_url",
    "source_index_url", "source_evidence_basis",
    "first_seen_local", "observation", "review_reason", "buyer_verified",
    "open_procurement_verified", "verification_required",
)
COMMERCIAL = re.compile(
    r"\b(?:industrial|manufactur\w*|factory|warehouse|distribution|logistics|"
    r"commercial|retail|shopping|office|hotel|hospital|healthcare|medical|clinic|"
    r"data.cent(?:re|er)|business.park|storage|employment|institutional|"
    r"service.centre|processing.facility|mixed.use)\b", re.I)
SUDBURY_FILE = re.compile(r"\bPL-[A-Z]{2,5}-20\d{2}-\d{3,6}\b", re.I)
NB_FILE = re.compile(
    r"\b(?:D1[0-6][-/ ]\d{2,4}[-/ ]\d{2,5}|"
    r"(?:ZBA|OPA|SPA|SUB|SPC)[-/ ]20\d{2}[-/ ]\d{1,5})\b", re.I)
NB_RELEVANT = re.compile(
    r"(?:zoning|official.plan|planning.application|development.application|"
    r"site.plan|subdivision|land.use|consent.application|planning.act)", re.I)
DATE_TEXT = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+20\d{2}\b", re.I)


def _clean(value):
    return " ".join(str(value or "").split())


def _date(value):
    if value in (None, "", 0):
        return ""
    if isinstance(value, (int, float)):
        try:
            # Esri date fields use milliseconds; None/0 are not valid dates.
            return dt.datetime.fromtimestamp(value / 1000, tz=dt.timezone.utc).date().isoformat()
        except (OSError, OverflowError, ValueError):
            return ""
    text = _clean(value)
    try:
        return dt.date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        pass
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def _safe_url(url, host, path_prefix):
    try:
        p = urlsplit(str(url or ""))
        return (p.scheme == "https" and p.hostname == host
                and p.port in (None, 443) and not p.username and not p.password
                and not p.fragment and p.path.startswith(path_prefix))
    except ValueError:
        return False


def _key(city, lane, ident):
    return "NORTH:" + hashlib.sha256(
        (city + "|" + lane + "|" + _clean(ident).upper()).encode("utf-8")
    ).hexdigest()[:24]


def _make(city, lane, ident, url, **values):
    result = {key: "" for key in FIELDS}
    result.update({
        "candidate_id": _key(city, lane, ident),
        "city": city, "source_lane": lane,
        "application_id": _clean(ident),
        "original_record_url": url,
        "publication_date_verified": "False", "buyer_verified": "False",
        "open_procurement_verified": "False",
        "verification_required": (
            "Verify original public disclosure, exact project identity, legal "
            "company role, scope and unawarded buying work before any sales use."),
    })
    for key, value in values.items():
        if key in FIELDS:
            result[key] = _clean(value)
    result["commercial_scope_text_match"] = str(bool(
        COMMERCIAL.search(result.get("scope", "") + " " + result.get("project_title", ""))))
    return result


def _write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            safe = {}
            for field in FIELDS:
                v = str(row.get(field, "") if row.get(field) is not None else "")
                safe[field] = "'" + v if v.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else v
            w.writerow(safe)


def _json(url, params, *, session_factory=requests.Session):
    if url not in BARRIE.values() and url not in [v + "/query" for v in BARRIE.values()]:
        raise ValueError("GIS_URL_NOT_IN_OFFICIAL_ALLOWLIST")
    if not _safe_url(url, "gispublic.barrie.ca", "/arcgis/rest/services/Open_Data/"):
        raise ValueError("GIS_URL_INVALID")
    if not public_dns("gispublic.barrie.ca", socket.getaddrinfo):
        raise ValueError("NONPUBLIC_OR_UNAVAILABLE_GIS_DNS")
    with session_factory() as session:
        session.trust_env = False
        session.headers.update({"User-Agent": AGENT, "Accept": "application/json"})
        prepared = requests.Request("GET", url, params=params).prepare()
        allowed, why = evaluate(session, prepared.url, AGENT, timeout=8)
        if not allowed:
            raise ValueError("GIS_ROBOTS_OR_ACCESS_DENIED:" + str(why))
        with session.get(prepared.url, timeout=(6, 18),
                         allow_redirects=False, stream=True) as resp:
            if resp.status_code != 200 or resp.url != prepared.url:
                raise ValueError("GIS_HTTP_" + str(resp.status_code) + "_OR_REDIRECT")
            if "json" not in resp.headers.get("Content-Type", "").lower():
                raise ValueError("GIS_NON_JSON_RESPONSE")
            raw = bytearray()
            for chunk in resp.iter_content(65536):
                raw.extend(chunk)
                if len(raw) > MAX_BYTES:
                    raise ValueError("GIS_RESPONSE_TOO_LARGE")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("error"):
            raise ValueError("GIS_ERROR_OR_INVALID_JSON")
        return data


def _barrie_fields(lane):
    if lane == "PLANNING":
        return {"id":"File_No", "address":"Address_Location",
                "scope":"Description_Proposal", "status":"Status",
                "company":"Applicant_Owner", "received":"Date_Application_Received",
                "type":"Application_Type", "title":"Phase"}
    if lane == "ISSUED_PERMITS":
        return {"id":"RECORD_ID", "address":"Full_Address",
                "scope":"Description", "status":"RECORD_STATUS",
                "received":"Date_Status", "type":"Sub_Type",
                "company":"", "title":""}
    return {"id":"", "address":"", "scope":"", "status":"RECORD_STATUS",
            "received":"Date_Opened", "type":"Sub_Type", "company":"", "title":""}


def _barrie(lane, fetch_json=None, *, today=None, max_pages=None):
    """Bounded official GIS. Active-permit layer has no public record ID."""
    today = today or dt.date.today()
    get = fetch_json or _json
    url = BARRIE[lane]
    meta = get(url, {"f":"json"})
    names = {str(x.get("name")) for x in meta.get("fields", [])
             if isinstance(x, dict) and x.get("name")}
    schema = _barrie_fields(lane)
    oid = meta.get("objectIdField") or "OBJECTID"
    required = {oid, schema["status"], schema["received"], schema["type"]}
    if schema["id"]:
        required.update({schema["id"], schema["address"], schema["scope"]})
    if not required.issubset(names):
        raise ValueError("BARRIE_GIS_SCHEMA_MISMATCH:" + ",".join(sorted(required-names)))
    if not schema["id"]:
        return [], {"status":"NO_PUBLISHED_PERMIT_NUMBER_HOLD",
                    "fields_seen":len(names),
                    "reason":"Active permit layer lacks file number and civic address"}
    pages = min(int(max_pages or MAX_BARRIE_PAGES[lane]), MAX_BARRIE_PAGES[lane])
    records = []
    last_count = 0
    last_transfer = False
    for p in range(pages):
        response = get(url + "/query", {
            "f":"json","where":"1=1", "outFields":"*",
            "returnGeometry":"false", "orderByFields":oid + " DESC",
            "resultOffset":str(p * PAGE_SIZE),
            "resultRecordCount":str(PAGE_SIZE),
        })
        features = response.get("features")
        if not isinstance(features, list):
            raise ValueError("BARRIE_GIS_QUERY_FEATURES_INVALID")
        last_count = len(features)
        last_transfer = bool(response.get("exceededTransferLimit"))
        for feature in features:
            a = feature.get("attributes") if isinstance(feature, dict) else None
            if not isinstance(a, dict):
                raise ValueError("BARRIE_INVALID_GIS_FEATURE")
            ident = _clean(a.get(schema["id"]))
            if not ident:
                continue
            proposal = _clean(a.get(schema["scope"]))
            status = _clean(a.get(schema["status"]))
            received = _date(a.get(schema["received"]))
            if received and received > today.isoformat():
                received = ""
            kind = "OFFICIAL_BARRIE_PLANNING_APPLICATION" if lane=="PLANNING" else "OFFICIAL_BARRIE_ISSUED_PERMIT"
            row = _make("Barrie", "BARRIE_" + lane, ident, url,
                record_kind=kind, project_title=_clean(a.get(schema["title"])) if schema["title"] else "",
                address=_clean(a.get(schema["address"])),
                scope=proposal, current_status=status,
                applicant_name_source_claim=_clean(a.get(schema["company"])) if schema["company"] else "",
                source_date=received,
                source_date_basis=("OFFICIAL_APPLICATION_RECEIVED_NOT_PUBLICATION"
                       if lane=="PLANNING" else "OFFICIAL_PERMIT_STATUS_DATE_NOT_PUBLICATION")
                       if received else "NO_VERIFIED_SOURCE_DATE",
                source_index_url=url,
                source_evidence_basis="OFFICIAL_BARRIE_GIS_FILE_NUMBER_NOT_VERIFIED_PUBLICATION")
            records.append(row)
        if last_count < PAGE_SIZE and not last_transfer:
            break
    seen = set()
    unique = []
    for row in records:
        if row["candidate_id"] not in seen:
            unique.append(row)
            seen.add(row["candidate_id"])
    sampled = last_count >= PAGE_SIZE or last_transfer
    return unique, {
        "status":"BOUNDED_GIS_SAMPLE_NOT_CITYWIDE" if sampled else "GIS_ROWS_FETCHED_NOT_FRESH_VERIFIED",
        "rows_fetched":len(records), "unique_file_numbers":len(unique),
        "sampled_or_truncated":sampled,
        "pages_limit":pages, "source":url,
        "initial_population_baseline_not_new_announcement":True,
    }


def _sudbury_sections(markup):
    soup = BeautifulSoup(markup, "html.parser")
    main = soup.find("main") or soup
    chunks = []
    # Prefer individual expandable records; fall back to project headings.
    for block in main.find_all(["details","article"]):
        content = _clean(block.get_text(" ", strip=True))
        if 60 <= len(content) <= 3500 and "Location" in content and "Application" in content:
            chunks.append(content)
    if not chunks:
        for h in main.find_all(["h2","h3","h4"]):
            heading = _clean(h.get_text(" ", strip=True))
            if len(heading) < 6 or len(heading) > 180 or heading.lower() in (
                    "pending planning applications", "application", "location"):
                continue
            parts = [heading]
            for node in h.find_next_siblings(limit=10):
                if node.name in ("h2","h3","h4"):
                    break
                v = _clean(node.get_text(" ", strip=True))
                if v:
                    parts.append(v[:1700])
                if sum(len(x) for x in parts) > 3000:
                    break
            content = " ".join(parts)
            if "Location" in content and "Application" in content:
                chunks.append(content)
    return list(dict.fromkeys(chunks))[:300]


def _sudbury(markup):
    found = []
    for block in _sudbury_sections(markup):
        m = re.search(r"\bLocation\s*:\s*(.{8,360}?)\s+Application\s*:", block, re.I)
        if not m:
            continue
        address = _clean(m.group(1))
        chunks = re.split(r"\bApplication\s*:", block, maxsplit=1, flags=re.I)
        scope = _clean(chunks[-1])[:1100]
        ids = list(dict.fromkeys(SUDBURY_FILE.findall(block)))
        if not COMMERCIAL.search(scope):
            continue
        head = _clean(block[:m.start()]).strip(" :;-")[:180]
        if not head or len(head) < 4:
            continue
        date_m = re.search(r"\b(?:Date Received|Received|Application Received)\s*:\s*("
                            + DATE_TEXT.pattern + r")", block, re.I)
        # An unnumbered but named official project is still worth research,
        # but is explicitly NOT an application-ID record or verified new lead.
        for ident in ids or [head + "|" + address]:
            exact = bool(ids)
            result = _make("Greater Sudbury", "SUDBURY_PENDING_PLANNING",
                ident.upper() if exact else ident, SUDBURY,
                record_kind=("OFFICIAL_PENDING_PLANNING_APPLICATION" if exact
                             else "PENDING_PROJECT_SIGNAL_NO_EXACT_FILE_ID"),
                application_id=ident.upper() if exact else "",
                project_title=head, address=address, scope=scope,
                applicant_name_source_claim=head,
                source_date=_date(date_m.group(1)) if date_m else "",
                source_date_basis=("OFFICIAL_APPLICATION_RECEIVED_NOT_PUBLICATION"
                                   if date_m else "NO_VERIFIED_SOURCE_DATE"),
                current_status="PENDING_APPLICATION_NOT_AN_APPROVAL",
                source_index_url=SUDBURY,
                source_evidence_basis=("EXACT_FILE_NUMBER_IN_OFFICIAL_PENDING_PAGE"
                    if exact else "NAMED_PROJECT_NO_EXACT_APPLICATION_ID"))
            if not exact:
                result["application_id"] = ""
            found.append(result)
    return list({x["candidate_id"]:x for x in found}.values())


def _sudbury_official_notice_documents(markup):
    # The main Sudbury pending-applications page returned a JS/index shell in
    # the Nov 17 live crawl. Its sibling upcoming-docs directory does publish
    # official dated notice PDFs. These are DOCUMENT LINKS, NOT applications.
    soup = BeautifulSoup(markup, "html.parser")
    main = soup.find("main") or soup
    result = []
    seen = set()
    for a in main.find_all("a", href=True):
        title = _clean(a.get_text(" ", strip=True))
        url = urljoin(SUDBURY_DOC_INDEX, str(a["href"]))
        parsed = urlsplit(url)
        if (not _safe_url(url, "www.greatersudbury.ca",
                          urlsplit(SUDBURY_DOC_INDEX).path)
                or parsed.query or parsed.path.rstrip("/") ==
                    urlsplit(SUDBURY_DOC_INDEX).path.rstrip("/")
                or url in seen or not title):
            continue
        # No PDF is parsed here, no file ID is fabricated from a date/slug.
        seen.add(url)
        result.append({
            "city": "Greater Sudbury", "document_label": title[:150],
            "official_document_url": url,
            "publisher_index_url": SUDBURY_DOC_INDEX,
            "planning_application_id": "",
            "project_name": "", "source_published_date": "",
            "record_classification": "OFFICIAL_NOTICE_DOCUMENT_LINK_NOT_PROJECT",
            "verification_required":
                "Inspect official PDF, extract exact project application IDs, "
                "site, applicant, proposal, and original public notice date."
        })
        if len(result) >= 30:
            break
    return result


def _nb_links(markup):
    soup = BeautifulSoup(markup, "html.parser")
    main = soup.find("main") or soup
    seen, result = set(), []
    for a in main.find_all("a", href=True):
        text = _clean(a.get_text(" ", strip=True))
        url = urljoin(NORTH_BAY, a["href"])
        p = urlsplit(url)
        if (not _safe_url(url,"northbay.ca","/public-notices/")
                or p.path.rstrip("/") == "/public-notices"
                or not NB_RELEVANT.search(text + " " + p.path.replace("-", " "))
                or url in seen):
            continue
        seen.add(url)
        result.append((url,text))
        if len(result) >= MAX_NB_DETAILS:
            break
    return result


def _nb_detail(markup, url):
    if not _safe_url(url, "northbay.ca", "/public-notices/"):
        raise ValueError("NORTH_BAY_OFFICIAL_HOST_ONLY")
    soup = BeautifulSoup(markup, "html.parser")
    main = soup.find("main") or soup
    h = main.find("h1")
    if h is None:
        raise ValueError("NORTH_BAY_MISSING_NOTICE_TITLE")
    title = _clean(h.get_text(" ", strip=True))
    body = _clean(main.get_text(" ", strip=True))
    if not NB_RELEVANT.search(title + " " + body[:400]):
        raise ValueError("NORTH_BAY_NOT_PLANNING_NOTICE")
    # Metadata date must be a dedicated time element; arbitrary meetings,
    # decision dates and policy effective dates are NOT notice posting dates.
    time_node = main.find("time", attrs={"datetime":True})
    published = _date(time_node.get("datetime")) if time_node else ""
    ids = list(dict.fromkeys(NB_FILE.findall(body)))
    file_id = ids[0] if len(ids)==1 else ""
    # If no exact application file number is published, this is a notice
    # signal only, not a planning application/lead. The URL is its key.
    scope = body[body.find(title)+len(title):][:1100] if title in body else body[:1100]
    addr = re.search(r"\b(?:located at|lands at|property at)\s+([0-9]{1,5}\s+[^.,;]{4,100})",
                     body, re.I)
    # The November 17 source scan mistakenly accepted a citywide ADU zoning
    # POLICY consultation as a development lead. Require a specific planning
    # file ID or civic project site before retaining notice evidence.
    if not file_id and not addr:
        raise ValueError("NON_PROJECT_POLICY_NOTICE_NO_FILE_ID_OR_CIVIC_SITE")
    return _make("North Bay","NORTH_BAY_OFFICIAL_PLANNING_NOTICE",
        file_id or url, url,
        record_kind=("EXACT_APPLICATION_FILE_ID" if file_id
                     else "OFFICIAL_NOTICE_LINK_ONLY_NO_APPLICATION_ID"),
        application_id=file_id,
        project_title=title,
        address=_clean(addr.group(1)) if addr else "",
        scope=scope, current_status="PUBLIC_NOTICE_NOT_ACTIVE_PROCUREMENT",
        source_date=published,
        source_date_basis="OFFICIAL_NOTICE_TIME_METADATA_NOT_FIRST_DISCLOSURE"
                          if published else "NO_VERIFIED_SOURCE_DATE",
        source_index_url=NORTH_BAY,
        source_evidence_basis=("OFFICIAL_NOTICE_WITH_EXACT_FILE_ID" if file_id
                               else "OFFICIAL_NOTICE_WITHOUT_EXACT_FILE_ID"))


def run(results, *, today=None, html_fetch=None, json_fetch=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_DIRECTORY_REQUIRED")
    day = today or dt.date.today()
    fetch_html = html_fetch or official_html
    prior_path = root / LEDGER_FILE
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.is_file() else {}
    if not isinstance(prior, dict) or prior.get("schema",1)!=1 or not isinstance(prior.get("records",{}),dict):
        raise ValueError("INVALID_NORTHERN_CITY_LEDGER")
    old = prior.get("records",{})
    state = dict(old)
    rows, changes, sources = [], [], []
    def keep(row):
        fingerprint = hashlib.sha256(json.dumps(
            {f:row[f] for f in FIELDS if f not in
             ("first_seen_local","observation","review_reason")},
            sort_keys=True).encode("utf-8")).hexdigest()
        before = old.get(row["candidate_id"])
        observed = ("INITIAL_BASELINE_NOT_NEW" if before is None else
                    "SOURCE_CHANGED_REVIEW" if before.get("digest")!=fingerprint else
                    "UNCHANGED")
        row["first_seen_local"]=(before or {}).get("first_seen_local",day.isoformat())
        row["observation"]=observed
        row["review_reason"]="SOURCE_TEXT_CHANGED_NOT_NEW_CONSTRUCTION_DISCLOSURE" if observed=="SOURCE_CHANGED_REVIEW" else ""
        rows.append(row)
        if observed=="SOURCE_CHANGED_REVIEW":
            changes.append(row)
        state[row["candidate_id"]]={
            "first_seen_local":row["first_seen_local"],"digest":fingerprint,
            "last_seen_local":day.isoformat()}
    for lane in BARRIE:
        status = {"city":"Barrie", "lane":lane, "source":BARRIE[lane],
                  "records":0,"status":"SOURCE_HELD"}
        try:
            recovered, audit = _barrie(lane,fetch_json=json_fetch,today=day)
            for row in recovered:
                keep(row)
            status.update(audit)
            status["records"] = len(recovered)
        except Exception as exc:
            status["error"]=type(exc).__name__+":"+str(exc)[:170]
        sources.append(status)
    sud = {"city":"Greater Sudbury","lane":"PENDING_PLANNING","source":SUDBURY,
           "records":0,"status":"SOURCE_HELD"}
    try:
        found = _sudbury(fetch_html(SUDBURY))
        for row in found:
            keep(row)
        sud["records"]=len(found)
        sud["status"]="EXACT_PUBLIC_APPLICATIONS_FOR_REVIEW" if found else "INDEX_ONLY_OR_NO_EXACT_COMMERCIAL_IDS"
    except Exception as exc:
        sud["error"]=type(exc).__name__+":"+str(exc)[:170]
    sources.append(sud)
    # Save official notice PDF link INDEX as a bounded human-research queue.
    # Empty main-page HTML does not establish that no applications exist.
    official_docs=[]
    try:
        official_docs=_sudbury_official_notice_documents(fetch_html(SUDBURY_DOC_INDEX))
        sud["supplemental_document_index_status"] = (
            "OFFICIAL_NOTICE_DOCUMENT_LINKS_ONLY" if official_docs else
            "NO_OFFICIAL_NOTICE_DOCUMENT_LINKS_FOUND")
    except Exception as exc:
        sud["supplemental_document_index_status"]="NOTICE_DOCUMENT_INDEX_HELD"
        sud["supplemental_document_index_error"] = type(exc).__name__+":"+str(exc)[:150]
    sud["supplemental_notice_document_links"] = len(official_docs)
    with (root / SUDBURY_DOC_LINKS).open("w", encoding="utf-8-sig", newline="") as stream:
        doc_fields = ("city", "document_label", "official_document_url",
            "publisher_index_url", "planning_application_id", "project_name",
            "source_published_date", "record_classification", "verification_required")
        writer = csv.DictWriter(stream, fieldnames=doc_fields)
        writer.writeheader()
        for line in official_docs:
            writer.writerow({key: (("'" + str(line[key])) if str(line[key]).lstrip().startswith(
                ("=", "+", "-", "@", "\\t", "\\r")) else line[key]) for key in doc_fields})
    nb = {"city":"North Bay","lane":"PUBLIC_PLANNING_NOTICES",
          "source":NORTH_BAY,"records":0,"status":"SOURCE_HELD",
          "notices_examined":0,"detail_errors":[],
          "policy_notices_excluded":0}
    try:
        links = []
        for pg in range(1,MAX_NB_PAGES+1):
            page = NORTH_BAY+"?page="+str(pg)
            links.extend(_nb_links(fetch_html(page)))
        unique = list(dict(links).items())[:MAX_NB_DETAILS]
        for url,_ in unique:
            try:
                row=_nb_detail(fetch_html(url),url)
                keep(row)
                nb["records"]+=1
            except ValueError as exc:
                if str(exc) == "NON_PROJECT_POLICY_NOTICE_NO_FILE_ID_OR_CIVIC_SITE":
                    nb["policy_notices_excluded"] += 1
                else:
                    nb["detail_errors"].append({"url":url,"error":
                        type(exc).__name__+":"+str(exc)[:150]})
            except Exception as exc:
                nb["detail_errors"].append({"url":url,"error":
                    type(exc).__name__+":"+str(exc)[:150]})
            nb["notices_examined"]+=1
        nb["status"]=("PARTIAL_NOTICE_SOURCE" if nb["detail_errors"] else
            "PUBLIC_NOTICES_WITH_PROJECT_CONTENT_REVIEW_ONLY" if nb["records"] else
            "NO_EXACT_PLANNING_NOTICES_DISCOVERED")
    except Exception as exc:
        nb["error"]=type(exc).__name__+":"+str(exc)[:170]
    sources.append(nb)
    _write(root / SOURCE_FILE, rows)
    _write(root / CHANGED_FILE, changes)
    if state != old:
        temp = prior_path.with_suffix(".tmp")
        temp.write_text(json.dumps({"schema":1,"records":state},indent=2),
                        encoding="utf-8")
        temp.replace(prior_path)
    audit = {
        "status":"NORTHERN_MAJOR_CITIES_EXPERIMENTAL_REVIEW_ONLY",
        "as_of":day.isoformat(),
        "total_evidence_records":len(rows),
        "source_changed_not_new_publications":len(changes),
        "source_details":sources,
        "verified_citywide_coverage":0,
        "new_cities_added_to_core_16":0,
        "buyers_verified":0,
        "first_project_publications_verified":0,
        "open_procurement_verified":0,
        "paid_ai_calls":0,
        "warning":"Barrie GIS application/permit event dates, Sudbury filing dates, "
                  "North Bay planning notice dates and local first-observed dates "
                  "are NOT confirmed first public construction announcements. "
                  "Application IDs not disclosed by the City are never invented.",
        "outputs":[SOURCE_FILE, CHANGED_FILE, STATUS_FILE, SUDBURY_DOC_LINKS],
    }
    (root/STATUS_FILE).write_text(json.dumps(audit,indent=2),
                                  encoding="utf-8")
    return audit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",required=True)
    args=p.parse_args()
    print(json.dumps(run(args.results),indent=2))


if __name__=="__main__":
    main()
