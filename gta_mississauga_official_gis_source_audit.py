"""Bounded, review-only official Mississauga application GIS source audit.

Does not touch Radar SQLite, assume publication dates, or create buyer leads.
Two City-published services: Site Plan and Rezoning applications.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import socket
from pathlib import Path
from urllib.parse import urlsplit

import requests

import robots_policy
from toronto_pdf_download import public_dns

ROOT = "https://services6.arcgis.com/hM5ymMLbxIyWTjn2/ArcGIS/rest/services/"
LAYERS = {
    "SITE_PLAN": ROOT + "Site_Plan_Applications/FeatureServer/0",
    "REZONING": ROOT + "Rezoning_Applications/FeatureServer/0",
}
NAMES = {"SITE_PLAN": "SitePlanApplications", "REZONING": "RezoningApplications"}
REQUIRED = {"OBJECTID", "APP_FILE_NO", "SITE_ADDRESS", "DESCRIPTION",
            "APPLICATION_DATE", "APPROVAL_DATE", "APPLICANT", "SIMPLE_STATUS",
            "TOTAL_NON_RES_GFA", "ICI_INDUST", "ICI_OFFICE", "ICI_RETAIL"}
OUT = "MISSISSAUGA_OFFICIAL_GIS_SOURCE_AUDIT.json"
USER_AGENT = "GTARadarResearch/1.0 (public Mississauga planning GIS)"
MAX_BYTES = 2_000_000
TIMEOUT = (8, 25)


def _fetch(url, params):
    if url not in LAYERS.values() and url not in {v + "/query" for v in LAYERS.values()}:
        raise ValueError("UNEXPECTED_MISSISSAUGA_ENDPOINT")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "services6.arcgis.com":
        raise ValueError("UNEXPECTED_MISSISSAUGA_HOST")
    if not public_dns(parts.hostname, socket.getaddrinfo):
        raise PermissionError("NO_PUBLIC_DNS")
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        allowed, reason = robots_policy.evaluate(session, url, USER_AGENT, timeout=TIMEOUT)
        if not allowed:
            raise PermissionError("ROBOTS_DENIED_" + str(reason))
        with session.get(url, params=params, timeout=TIMEOUT, stream=True,
                         allow_redirects=False) as response:
            if response.status_code != 200 or response.history:
                raise ValueError("HTTP_OR_REDIRECT_" + str(response.status_code))
            target = urlsplit(response.url)
            if target.scheme != parts.scheme or target.hostname != parts.hostname or target.path != parts.path:
                raise ValueError("REDIRECTED_ORIGIN")
            if "json" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("UNEXPECTED_CONTENT_TYPE")
            body = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise ValueError("RESPONSE_TOO_LARGE")
            data = json.loads(body)
            if not isinstance(data, dict) or data.get("error"):
                raise ValueError("ARCGIS_ERROR")
            return data
    finally:
        session.close()


def audit(out, *, fetch=False, fetcher=None, now=None):
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    at = now or dt.datetime.now(dt.timezone.utc)
    if at.tzinfo is None:
        raise ValueError("TIMEZONE_AWARE_TIMESTAMP_REQUIRED")
    report = {
        "status": "HOLD", "checked_utc": at.astimezone(dt.timezone.utc).isoformat(),
        "mode": "MISSISSAUGA_OFFICIAL_GIS_SOURCE_ACCEPTANCE_ONLY",
        "layers": [], "schema_valid_layers": 0, "id_inventory_complete_layers": 0,
        "unique_applications_collected": 0, "publisher_first_publications_verified": 0,
        "buyer_verified": 0, "open_procurement_verified": 0, "paid_ai_calls": 0,
        "warning": "APPLICATION_DATE is not first online publication. Data includes approvals since 2016. Applicant is not a confirmed buyer."
    }
    if not fetch:
        report["status"] = "EXPLICIT_MANUAL_FETCH_NOT_REQUESTED"
    else:
        query = fetcher or _fetch
        for layer, url in LAYERS.items():
            entry = {"layer": layer, "source_url": url, "status": "HOLD"}
            try:
                meta = query(url, {"f": "json"})
                names = {field.get("name") for field in meta.get("fields", [])
                         if isinstance(field, dict)}
                if (meta.get("name") != NAMES[layer] or
                        meta.get("objectIdField") != "OBJECTID" or
                        not REQUIRED.issubset(names)):
                    raise ValueError("OFFICIAL_SCHEMA_CHANGED")
                report["schema_valid_layers"] += 1
                ids = query(url + "/query", {
                    "f": "json", "where": "1=1", "returnIdsOnly": "true"})
                raw = ids.get("objectIds")
                if (not isinstance(raw, list) or not raw or len(raw) > 20000 or
                        any(type(x) is not int or x < 1 for x in raw) or
                        len(raw) != len(set(raw))):
                    raise ValueError("INVALID_OR_UNBOUNDED_OBJECT_IDS")
                entry.update(status="SCHEMA_AND_OBJECT_ID_INVENTORY_READY",
                             feature_count=len(raw),
                             service_last_edit_ms=(meta.get("editingInfo") or {}).get("dataLastEditDate"))
                report["id_inventory_complete_layers"] += 1
            except Exception as exc:
                entry.update(status="SOURCE_HELD", reason=type(exc).__name__ + ":" + str(exc)[:120])
            report["layers"].append(entry)
        report["status"] = ("BOTH_SOURCE_SCHEMAS_AND_ID_INVENTORIES_READY"
                            if report["id_inventory_complete_layers"] == 2
                            else "PARTIAL_OR_BLOCKED_OFFICIAL_GIS_SOURCE")
    (folder / OUT).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", required=True)
    cli.add_argument("--fetch", action="store_true")
    args = cli.parse_args()
    print(json.dumps(audit(args.out, fetch=args.fetch), indent=2))
