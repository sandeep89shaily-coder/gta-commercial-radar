"""Offline, provenance-first municipal source registry.

Normalize the repository's existing officially documented meeting-source CSV.
This is NOT a web crawler or a guarantee that a provider API is accessible.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit

REGISTRY = Path(__file__).resolve().parent / "config" / "municipal_document_sources.csv"
OUTPUT = "GTA_RADAR_MUNICIPAL_PLATFORM_REGISTRY.json"
REQUIRED = {"id", "city", "url", "system", "source_type", "status", "evidence"}
PROVIDERS = {
    "escribe": "ESCRIBE",
    "civicweb": "CIVICWEB",
    "civicclerk": "CIVICCLERK",
    "granicus": "GRANICUS",
    "legistar": "LEGISTAR",
    "laserfiche": "LASERFICHE",
    "tmmis": "TMMIS",
}


def provider(raw):
    """Only label providers explicitly indicated by the source registry."""
    lowered = str(raw or "").casefold()
    found = [label for needle, label in PROVIDERS.items() if needle in lowered]
    return found[0] if len(found) == 1 else "UNKNOWN"


def _official_url(value):
    parts = urlsplit(str(value or "").strip())
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.fragment or parts.port not in (None, 443)
            or parts.hostname in ("localhost", "127.0.0.1")):
        raise ValueError("INVALID_OFFICIAL_REGISTRY_URL")
    return parts.geturl()


def build(registry=REGISTRY, *, observed_at=None):
    with Path(registry).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("SOURCE_REGISTRY_SCHEMA_MISMATCH")
        rows = list(reader)
    if len(rows) > 300:
        raise ValueError("SOURCE_REGISTRY_TOO_LARGE")
    records, ids = [], set()
    for row in rows:
        identifier = (row.get("id") or "").strip()
        city = (row.get("city") or "").strip()
        if not identifier or not city or identifier in ids:
            raise ValueError("INVALID_OR_DUPLICATE_SOURCE_ID")
        ids.add(identifier)
        url = _official_url(row["url"])
        metadata = {
            "source_id": identifier, "city": city, "official_index_url": url,
            "platform": provider(row.get("system")),
            "platform_source_label": (row.get("system") or "").strip()[:120],
            "source_type": (row.get("source_type") or "").strip()[:120],
            "source_registry_status": (row.get("status") or "").strip()[:160],
            "registry_evidence_url": _official_url(row.get("evidence") or url),
            "retrieval_attempted": False,
            "records_retrieved": None,
            "official_record_completeness": "UNKNOWN",
            "publisher_first_publication_verified": False,
            "source_access_authorized_for_automation": "NOT_ESTABLISHED",
            "adaptation_status": "REGISTRY_ONLY",
        }
        records.append(metadata)
    return {
        "status": "REGISTERED_NOT_FETCHED",
        "observed_at_utc": observed_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_count": len(records),
        "distinct_cities": len({r["city"] for r in records}),
        "known_platform_sources": sum(r["platform"] != "UNKNOWN" for r in records),
        "warning": ("Registry entries identify published source indexes only. "
                    "No API access, source freshness, citywide coverage or "
                    "commercial project is established by this report."),
        "sources": records,
    }


def run(results, *, registry=REGISTRY):
    report = build(registry)
    destination = Path(results) / OUTPUT
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps({k: v for k, v in run(args.results).items()
                      if k != "sources"}, indent=2))
