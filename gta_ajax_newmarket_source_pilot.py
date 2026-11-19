"""Source adapters for Ajax and Newmarket ArcGIS planning applications.

STANDALONE RESEARCH PILOT. Never called by the production 24-city pipeline.
An explicit --fetch-approved flag is required for live network collection;
robots and publisher-reuse approval are operator responsibilities, and the
default mode only parses externally obtained approved JSON snapshots.
No DeepSeek, no outreach, no changes to collection database.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

SOURCES = {
    "Ajax": {
        "url": "https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/FeatureServer/3",
        "id": "REF_ID", "address": "ADDRESS", "description": "DESCRIPTION",
        "company": "APPLICANT", "stage": "STATUS", "category": "TYPE",
        "date": "SUBMISSION_DATE", "date_basis": "APPLICATION_SUBMITTED_NOT_PUBLICATION",
        "oid": "OBJECTID",
    },
    "Newmarket": {
        "url": "https://services3.arcgis.com/tSwsWwbYRimLwcCZ/ArcGIS/rest/services/OpenNewmarket_Developments/FeatureServer/23",
        "id": "FILE_NUM", "address": "LOCATION", "description": "DESCRIPTION",
        "company": "OWNER", "stage": "APP_STATUS", "category": "PROPOSE_LAND_USE",
        "date": "EDIT_WHEN", "date_basis": "GIS_LAST_EDIT_NOT_PUBLICATION",
        "oid": "OBJECTID",
    },
}
MAX_ROWS = 300
PAGE = 100
MAX_BYTES = 3_000_000
OUTPUT = "GTA_RADAR_AJAX_NEWMARKET_RESEARCH_APPLICATIONS.csv"
REPORT = "GTA_RADAR_AJAX_NEWMARKET_RESEARCH_STATUS.json"
FIELDS = ("city", "application_id", "address", "scope", "applicant_source_claim",
          "category", "current_status", "source_date", "source_date_basis",
          "source_url", "original_publication_verified",
          "buying_role_verified", "open_supplier_package_verified",
          "record_status", "source_oid_for_diagnostics_only")
TRADES = re.compile(r"\\b(?:industrial|manufactur\\w*|warehouse|logistic\\w*|"
                    r"commercial|retail|office|hotel|data.cent(?:re|er)|"
                    r"storage|institutional|mixed.use|factory|"
                    r"distribution|medical|business.park)\\b", re.I)

def _text(value, cap=500):
    return " ".join(str(value or "").split())[:cap]

def _date(value):
    # ArcGIS milliseconds are NOT publisher's first publication date.
    if isinstance(value, (float, int)) and value > 1_000_000_000_000:
        try:
            return dt.datetime.fromtimestamp(value / 1000, dt.timezone.utc).date().isoformat()
        except (OverflowError, ValueError, OSError):
            return ""
    raw = _text(value)
    if re.fullmatch(r"20\\d{2}-\\d{2}-\\d{2}", raw):
        try:
            return dt.date.fromisoformat(raw).isoformat()
        except ValueError:
            return ""
    return ""

def parse(city, page, *, permit_source_link=True):
    """Parse approved ArcGIS JSON WITHOUT accepting synthetic object IDs as file IDs."""
    if city not in SOURCES or not isinstance(page, dict):
        raise ValueError("UNRECOGNIZED_CITY_OR_RESPONSE")
    if page.get("error"):
        raise ValueError("ARCGIS_ERROR")
    features = page.get("features")
    if not isinstance(features, list):
        raise ValueError("FEATURES_ARRAY_REQUIRED")
    config = SOURCES[city]
    rows, seen = [], set()
    for feature in features:
        if not isinstance(feature, dict) or not isinstance(feature.get("attributes"), dict):
            continue
        a = feature["attributes"]
        ident = _text(a.get(config["id"]), 130)
        address = _text(a.get(config["address"]), 220)
        scope = _text(a.get(config["description"]), 1400)
        if not ident or not address or not scope:
            continue
        # Distinct multipart geometries for one file must not become distinct
        # application IDs. File numbers can be reused: manual audit follows.
        key = ident.casefold()
        if key in seen:
            continue
        seen.add(key)
        evidence_url = _text(a.get("WEBLINK") or a.get("WEBSITE") or
                             a.get("DOC_LINK") or a.get("IMO_URL"), 600)
        p = urlsplit(evidence_url)
        if not (p.scheme == "https" and p.hostname and not p.username
                and not p.password):
            evidence_url = config["url"] if permit_source_link else ""
        category = _text(a.get(config["category"]), 100)
        if city == "Ajax":
            # Multiple declared land-use tags; never call all land uses industrial.
            category = " | ".join(x for x in dict.fromkeys([
                category, _text(a.get("TYPE_2"), 100), _text(a.get("TYPE_3"), 100)])
                if x)
        rows.append({
            "city": city, "application_id": ident, "address": address,
            "scope": scope, "applicant_source_claim": _text(a.get(config["company"]), 220),
            "category": category, "current_status": _text(a.get(config["stage"]), 120),
            "source_date": _date(a.get(config["date"])),
            "source_date_basis": config["date_basis"],
            "source_url": evidence_url,
            "original_publication_verified": "False",
            "buying_role_verified": "False",
            "open_supplier_package_verified": "False",
            "record_status": ("COMMERCIAL_SCOPE_REVIEW_ONLY" if TRADES.search(
                category + " " + scope) else "NONCOMMERCIAL_OR_UNCLEAR"),
            "source_oid_for_diagnostics_only": _text(a.get(config["oid"]), 30),
        })
    return rows

def _fetch(url, *, opener=None):
    if not url.startswith("https://"):
        raise ValueError("HTTPS_REQUIRED")
    fetch = opener or urlopen
    req = Request(url, headers={"User-Agent": "GTA-Radar-source-research/1.0"})
    with fetch(req, timeout=20) as response:
        # Allow only exact expected origin and capped response sizes.
        final = response.geturl()
        if urlsplit(final).netloc != urlsplit(url).netloc:
            raise ValueError("CROSS_HOST_REDIRECT_BLOCKED")
        payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError("SOURCE_RESPONSE_TOO_LARGE")
    return json.loads(payload.decode("utf-8"))

def _robots_approved(url):
    origin = urlsplit(url)
    robot = RobotFileParser()
    robot.set_url(origin.scheme + "://" + origin.netloc + "/robots.txt")
    try:
        robot.read()
        return robot.can_fetch("GTA-Radar-source-research", url)
    except (OSError, ValueError):
        return False

def query(city, *, fetcher=None, max_rows=MAX_ROWS, robots_check=True):
    """Bounded remote fetch ONLY after explicit publisher-approval decision."""
    if city not in SOURCES or not 1 <= max_rows <= MAX_ROWS:
        raise ValueError("CITY_OR_ROW_CAP_INVALID")
    base = SOURCES[city]["url"]
    if robots_check and not _robots_approved(base + "/query"):
        raise PermissionError("ROBOTS_OR_TERMS_NOT_VERIFIED")
    get = fetcher or _fetch
    allrows, seen_oids = [], set()
    for offset in range(0, max_rows, PAGE):
        parameters = {
            "where": "1=1", "outFields": "*", "returnGeometry": "false",
            "orderByFields": "OBJECTID ASC",
            "resultOffset": str(offset), "resultRecordCount": str(
                min(PAGE, max_rows - offset)), "f": "json",
        }
        url = base + "/query?" + urlencode(parameters)
        page = get(url)
        if not isinstance(page, dict) or page.get("error") or not isinstance(
                page.get("features"), list):
            raise ValueError("INVALID_ARCGIS_QUERY_RESPONSE")
        features = page["features"]
        if len(features) > min(PAGE, max_rows - offset):
            raise ValueError("PAGE_EXCEEDS_REQUEST")
        for feature in features:
            oid = str((feature.get("attributes") or {}).get("OBJECTID") or "")
            if not oid or oid in seen_oids:
                raise ValueError("MISSING_OR_DUPLICATE_OBJECTID_ACROSS_PAGES")
            seen_oids.add(oid)
        allrows.extend(features)
        if len(features) < min(PAGE, max_rows - offset):
            break
    return parse(city, {"features": allrows})

def write(root, rows, *, modes):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    out = root / OUTPUT
    dedup = {}
    for row in rows:
        key = (row["city"], row["application_id"].casefold())
        dedup.setdefault(key, row)
    with out.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        for row in dedup.values():
            writer.writerow({key: ("'" + str(row.get(key) or "")
                if str(row.get(key) or "").lstrip().startswith(
                    ("=", "+", "-", "@", "\\t", "\\r"))
                else str(row.get(key) or "")) for key in FIELDS})
    status = {
        "status": "ISOLATED_SOURCE_RESEARCH_NOT_PRODUCTION",
        "city_modes": modes, "candidate_rows": len(dedup),
        "commercial_research_rows": sum(x["record_status"] ==
            "COMMERCIAL_SCOPE_REVIEW_ONLY" for x in dedup.values()),
        "verified_buyers": 0, "verified_original_publications": 0,
        "verified_open_packages": 0,
        "production_municipalities_unchanged": True,
        "source_completeness_not_verified": True,
        "csv": str(out),
    }
    (root / REPORT).write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", required=True)
    ap.add_argument("--snapshot-dir", help="Folder with ajax.json and newmarket.json")
    ap.add_argument("--fetch-approved", action="store_true",
                    help="ONLY with separate documented permission to query both sources")
    args = ap.parse_args()
    if args.fetch_approved and args.snapshot_dir:
        ap.error("Use snapshots OR explicit approved fetch, not both")
    rows, modes = [], {}
    for city in SOURCES:
        if args.fetch_approved:
            rows.extend(query(city))
            modes[city] = "BOUNDED_LIVE_FETCH_OPERATOR_APPROVED"
        elif args.snapshot_dir:
            path = Path(args.snapshot_dir) / (city.lower() + ".json")
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_BYTES:
                rows.extend(parse(city, json.loads(path.read_text(encoding="utf-8"))))
                modes[city] = "OFFLINE_APPROVED_SNAPSHOT"
            else:
                modes[city] = "SNAPSHOT_MISSING"
        else:
            modes[city] = "NO_SOURCE_FETCH_PREFLIGHT"
    print(json.dumps(write(args.results, rows, modes=modes), indent=2))

if __name__ == "__main__":
    main()
