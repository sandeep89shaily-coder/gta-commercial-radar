"""Official Brampton pre-consultation, OPA/ZBA and site-plan ArcGIS collector.

Three City of Brampton-published feature layers in the same ArcGIS item.
Complete, bounded OBJECTID list is retrieved before exact-id batched records.
Never infer first publication, buyer or open procurement from GIS dates.
Manual and review-only: no original Radar SQLite writes or paid AI.
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
from urllib.parse import urlsplit

import requests

import robots_policy
from toronto_pdf_download import public_dns

BASE = ("https://services3.arcgis.com/rl7ACuZkiFsmDA2g/ArcGIS/rest/services/"
        "Planning_Land_Use_Development/FeatureServer")
LAYERS = {9: "OPA_ZBA_SUBDIVISION", 10: "PRE_CONSULTATION", 11: "SITE_PLAN_APPROVAL"}
EXPECTED = {"FILE_NUMBER", "LOCATION", "DATE_RECEIVED", "APPLICATION_TYPE",
            "APPLICATION_TITLE", "DESCRIPTION", "STATUS", "PROPOSAL_DESCRIPTION",
            "AGENT_COMPANY", "APPLICANT_COMPANY", "POLY_ID"}
FIELD_LIST = ",".join(sorted(EXPECTED))
AGENT = "GTARadarResearch/1.0 (public Brampton planning GIS)"
MAX_BYTES = 6_000_000
MAX_IDS = 12000
BATCH_SIZE = 250
TIMEOUT = (8, 25)
ALL = "BRAMPTON_OFFICIAL_GIS_APPLICATIONS_REVIEW.csv"
CHANGED = "BRAMPTON_OFFICIAL_GIS_CHANGES_REVIEW.csv"
LEDGER = "BRAMPTON_OFFICIAL_GIS_FIRST_OBSERVED.json"
STATUS = "BRAMPTON_OFFICIAL_GIS_SOURCE_STATUS.json"
COLUMNS = (
    "city", "layer", "application_id", "location", "application_type",
    "application_title", "description", "proposal_description", "status",
    "applicant_company_source_text", "agent_company_source_text",
    "date_received_utc", "date_received_basis", "source_layer_url",
    "first_observed_utc", "last_observed_utc", "observation",
    "commercial_screen", "original_publication_date_verified",
    "project_verified", "buyer_verified", "open_procurement_verified"
)
COMMERCIAL = re.compile(
    r"\b(?:industrial|warehouse|factory|commercial|manufactur\w*|"
    r"office|retail|hotel|restaurant|distribution|logistics|employment|"
    r"business|data.cent(?:er|re)|storage|industrial.park)\b", re.I
)
CLOSED = re.compile(r"\b(?:withdrawn|cancelled|refused)\b", re.I)


def _clean(value, cap=700):
    return " ".join(str(value or "").split())[:cap]


def _date_received(value):
    """ArcGIS date milliseconds; not online publication or first detection."""
    if value is None or isinstance(value, bool):
        return ""
    try:
        stamp = float(value)
        if not 0 < stamp < 4_000_000_000_000:
            return ""
        return dt.datetime.fromtimestamp(stamp / 1000,
                                         tz=dt.timezone.utc).date().isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        return ""


def _network(url, params):
    prefix = urlsplit(BASE)
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != prefix.hostname
            or not parts.path.startswith(prefix.path + "/")
            or not re.fullmatch(r"/(?:9|10|11)(?:/query)?",
                                parts.path[len(prefix.path):])
            or parts.username or parts.password or parts.port not in (None, 443)
            or parts.query or parts.fragment):
        raise ValueError("UNEXPECTED_BRAMPTON_GIS_URL")
    if not public_dns(parts.hostname, socket.getaddrinfo):
        raise ValueError("ARCGIS_PUBLIC_DNS_UNAVAILABLE")
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": AGENT, "Accept": "application/json"})
    try:
        allowed, reason = robots_policy.evaluate(
            session, url, AGENT, timeout=TIMEOUT)
        if not allowed:
            raise PermissionError("ARCGIS_ROBOTS_" + str(reason))
        with session.get(url, params=params, stream=True,
                         timeout=TIMEOUT, allow_redirects=False) as response:
            if response.status_code != 200 or response.history:
                raise ValueError("ARCGIS_HTTP_OR_REDIRECT_" + str(response.status_code))
            if (urlsplit(response.url).hostname != parts.hostname
                    or urlsplit(response.url).path != parts.path):
                raise ValueError("ARCGIS_RESPONSE_ORIGIN_CHANGED")
            if "json" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("ARCGIS_UNEXPECTED_CONTENT_TYPE")
            buf = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    buf.extend(chunk)
                    if len(buf) > MAX_BYTES:
                        raise ValueError("ARCGIS_RESPONSE_TOO_LARGE")
            result = json.loads(bytes(buf))
            if not isinstance(result, dict) or result.get("error"):
                raise ValueError("ARCGIS_API_ERROR")
            return result
    finally:
        session.close()


def _get_layer(number, query):
    url = BASE + "/" + str(number)
    metadata = query(url, {"f": "json"})
    fields = metadata.get("fields")
    if (not isinstance(fields, list) or
            metadata.get("id") != number or
            metadata.get("name", "").casefold() !=
                {9: "opa zba subdivision", 10: "pre consultation",
                 11: "site plan approval"}[number] or
            metadata.get("objectIdField") != "POLY_ID" or
            not EXPECTED.issubset({item.get("name") for item in fields
                                  if isinstance(item, dict)})):
        raise ValueError("BRAMPTON_OFFICIAL_LAYER_SCHEMA_MISMATCH")
    qurl = url + "/query"
    identifiers = query(qurl, {
        "f": "json", "where": "1=1", "returnIdsOnly": "true"})
    raw_ids = identifiers.get("objectIds")
    if (not isinstance(raw_ids, list) or
            not 0 < len(raw_ids) <= MAX_IDS or
            any(type(x) is not int or x < 1 for x in raw_ids)):
        raise ValueError("BRAMPTON_ID_INVENTORY_MISSING_OR_OUT_OF_BOUNDS")
    ids = sorted(set(raw_ids))
    if len(ids) != len(raw_ids):
        raise ValueError("BRAMPTON_DUPLICATE_GIS_IDS")
    result = []
    for offset in range(0, len(ids), BATCH_SIZE):
        part = ids[offset:offset + BATCH_SIZE]
        response = query(qurl, {
            "f": "json", "objectIds": ",".join(map(str, part)),
            "outFields": FIELD_LIST, "returnGeometry": "false"})
        features = response.get("features")
        if not isinstance(features, list):
            raise ValueError("BRAMPTON_GIS_FEATURE_LIST_MISSING")
        found = {}
        for feature in features:
            attributes = feature.get("attributes") if isinstance(feature, dict) else None
            if not isinstance(attributes, dict):
                raise ValueError("BRAMPTON_GIS_FEATURE_ATTRIBUTES_MISSING")
            object_id = attributes.get("POLY_ID")
            if type(object_id) is not int or object_id not in part or object_id in found:
                raise ValueError("BRAMPTON_GIS_UNEXPECTED_OR_DUPLICATE_OBJECT_ID")
            found[object_id] = attributes
        if set(found) != set(part):
            raise ValueError("BRAMPTON_GIS_INCOMPLETE_BATCH_NO_BASELINE")
        result.extend(found[x] for x in part)
    return result, metadata.get("editingInfo", {}).get("dataLastEditDate")


def _records(layer, attributes):
    by_file = {}
    held = 0
    conflicted = set()
    for attrs in attributes:
        ident = _clean(attrs.get("FILE_NUMBER"), 100).upper()
        if (not ident or not any(char.isdigit() for char in ident)
                or not re.fullmatch(r"[A-Z0-9][A-Z0-9 /_.-]{3,99}", ident)):
            held += 1
            continue
        description = _clean(attrs.get("DESCRIPTION"))
        proposal = _clean(attrs.get("PROPOSAL_DESCRIPTION"), 1200)
        title = _clean(attrs.get("APPLICATION_TITLE"), 300)
        location = _clean(attrs.get("LOCATION"), 250)
        if not (location or title) or not (description or proposal or title):
            held += 1
            continue
        row = {
            "city": "Brampton", "layer": LAYERS[layer],
            "application_id": ident, "location": location,
            "application_type": _clean(attrs.get("APPLICATION_TYPE"), 90),
            "application_title": title, "description": description,
            "proposal_description": proposal,
            "status": _clean(attrs.get("STATUS"), 80),
            "applicant_company_source_text": _clean(attrs.get("APPLICANT_COMPANY"), 200),
            "agent_company_source_text": _clean(attrs.get("AGENT_COMPANY"), 200),
            "date_received_utc": _date_received(attrs.get("DATE_RECEIVED")),
            "date_received_basis": ("GIS_DATE_RECEIVED_NOT_FIRST_PUBLICATION"
                                    if _date_received(attrs.get("DATE_RECEIVED"))
                                    else "GIS_DATE_RECEIVED_UNAVAILABLE"),
            "source_layer_url": BASE + "/" + str(layer),
            "commercial_screen": ("COMMERCIAL_KEYWORD_REVIEW_ONLY"
                if COMMERCIAL.search(title + " " + description + " " + proposal)
                and not CLOSED.search(_clean(attrs.get("STATUS")))
                else "NOT_QUALIFIED_OR_CLOSED_REVIEW"),
            "original_publication_date_verified": False,
            "project_verified": False, "buyer_verified": False,
            "open_procurement_verified": False
        }
        if ident in conflicted:
            continue
        if ident in by_file:
            # Multiple geographic polygons for the same file are legitimate
            # only if the key non-geographic source facts agree.
            compare = ("application_type", "application_title",
                       "description", "proposal_description",
                       "status", "applicant_company_source_text")
            if any(row[k] != by_file[ident][k] for k in compare):
                conflicted.add(ident)
                del by_file[ident]
                held += 1
        else:
            by_file[ident] = row
    return list(by_file.values()), held


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for item in rows:
            writer.writerow({
                k: ("'" + str(value) if str(value).lstrip().startswith(
                    ("=", "+", "-", "@")) else value)
                for k, value in item.items()
            })


def run(folder, *, fetch=False, fetcher=None, now=None):
    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    clock = now or dt.datetime.now(dt.timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("TIMEZONE_AWARE_NOW_REQUIRED")
    at = clock.astimezone(dt.timezone.utc).isoformat()
    status = {
        "status": "HOLD", "checked_utc": at,
        "source": BASE, "layers_checked": 0, "layers_complete": 0,
        "applications_currently_extracted": 0, "first_observed_on_complete_layers": 0,
        "changed_application_records_review_only": 0,
        "verified_first_publications": 0, "verified_buyers": 0,
        "verified_supplier_packages": 0, "paid_ai_calls": 0,
        "layer_results": [],
        "warning": "GIS data-received is not first publication; first observation is not new development. "
                   "Applicant is not verified purchasing authority. No commercial bids verified."
    }
    if not fetch:
        status["status"] = "FRESH_MANUAL_SOURCE_FETCH_NOT_REQUESTED"
        (dest / STATUS).write_text(json.dumps(status, indent=2), encoding="utf-8")
        return status
    ledger_file = dest / LEDGER
    try:
        prior = json.loads(ledger_file.read_text(encoding="utf-8")) if ledger_file.is_file() else {
            "version": 1, "items": {}
        }
        if prior.get("version") != 1 or not isinstance(prior.get("items"), dict):
            raise ValueError("BRAMPTON_GIS_LEDGER_SCHEMA_UNRECOGNIZED")
        next_items = dict(prior["items"])
        collected, changed = [], []
        for number, name in LAYERS.items():
            entry = {"layer": number, "name": name, "status": "HOLD"}
            status["layers_checked"] += 1
            try:
                attrs, last_edit = _get_layer(number, fetcher or _network)
                rows, held = _records(number, attrs)
                # A complete official object-ID snapshot is necessary before
                # comparing history. Zero valid files is not a clean scrape.
                if not rows:
                    raise ValueError("NO_USABLE_OFFICIAL_APPLICATION_FILES")
                for row in rows:
                    key = str(number) + ":" + row["application_id"]
                    digest = hashlib.sha256(json.dumps({
                        k: row[k] for k in (
                            "application_type", "application_title",
                            "description", "proposal_description", "location",
                            "status", "applicant_company_source_text",
                            "agent_company_source_text", "date_received_utc")
                    }, sort_keys=True).encode()).hexdigest()
                    old = prior["items"].get(key)
                    event = ("BASELINE_EXISTING_NOT_NEW_PUBLICATION" if not old
                             else "SOURCE_RECORD_CHANGED_NOT_NEW_PUBLICATION"
                             if old.get("source_sha256") != digest else "UNCHANGED")
                    row.update(first_observed_utc=old.get("first_observed_utc", at)
                               if old else at, last_observed_utc=at,
                               observation=event)
                    next_items[key] = {"first_observed_utc": row["first_observed_utc"],
                                       "last_observed_utc": at,
                                       "source_sha256": digest}
                    collected.append(row)
                    if event == "SOURCE_RECORD_CHANGED_NOT_NEW_PUBLICATION":
                        changed.append(row)
                entry.update(status="COMPLETE_REVIEW_ONLY",
                             polygons=len(attrs), unique_application_files=len(rows),
                             records_held=held,
                             publisher_layer_last_edit_ms=last_edit)
                status["layers_complete"] += 1
            except Exception as exc:
                entry.update(status="SOURCE_FAILED_PRIOR_HISTORY_PRESERVED",
                             reason=type(exc).__name__ + ":" + str(exc)[:160])
            status["layer_results"].append(entry)
        status["applications_currently_extracted"] = len(collected)
        status["changed_application_records_review_only"] = len(changed)
        status["first_observed_on_complete_layers"] = sum(
            row["observation"] == "BASELINE_EXISTING_NOT_NEW_PUBLICATION"
            for row in collected)
        if not collected:
            status["status"] = "ALL_OFFICIAL_GIS_LAYERS_HELD_NO_LEDGER_MUTATION"
            return status
        _write_csv(dest / ALL, collected)
        _write_csv(dest / CHANGED, changed)
        temporary = dest / (LEDGER + ".tmp")
        temporary.write_text(json.dumps({
            "version": 1, "updated_utc": at, "items": next_items
        }, indent=2), encoding="utf-8")
        temporary.replace(ledger_file)
        status["status"] = ("ALL_THREE_LAYERS_REVIEW_ONLY" if
                            status["layers_complete"] == len(LAYERS)
                            else "PARTIAL_OFFICIAL_GIS_LAYERS_REVIEW_ONLY")
    except Exception as exc:
        status["status"] = "OFFICIAL_GIS_COLLECTOR_FAILED_NO_BASELINE"
        status["error_type"] = type(exc).__name__
        status["error_reason"] = str(exc)[:180]
    finally:
        (dest / STATUS).write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", required=True)
    cli.add_argument("--fetch", action="store_true")
    args = cli.parse_args()
    print(json.dumps(run(args.out, fetch=args.fetch), indent=2))


if __name__ == "__main__":
    main()
