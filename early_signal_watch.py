"""Read-only early planning signals for GTA Radar. No paid APIs or V8 changes.

This pilot keeps its own SQLite history and produces REVIEW_ONLY reports. A first
snapshot is a baseline (never a new business opportunity). No missing record is
treated as cancelled, and an application is not proof of procurement intent.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from early_signal_quality import (QUALITY_VERSION, classify as quality_classify,
                                  source_date as get_source_date, export_project_reports)

ROOT = Path(__file__).resolve().parent
BRAMPTON = ("https://services3.arcgis.com/rl7ACuZkiFsmDA2g/ArcGIS/rest/"
            "services/Planning_Land_Use_Development/FeatureServer/")
MISSAUGA = ("https://services6.arcgis.com/hM5ymMLbxIyWTjn2/ArcGIS/rest/"
            "services/")
YORK = ("https://services1.arcgis.com/GzvOwaQBbX7KLiuG/ArcGIS/rest/"
        "services/Hosted_Development_Application_Status_And_Teams/FeatureServer/0")
TORONTO = ("https://gis.toronto.ca/arcgis/rest/services/cot_geospatial11/FeatureServer/60")

# These are deliberately separate from config/sources.json and the paid queue.
# URLs are official GIS layers; York is REGION-WIDE, not a verified Vaughan feed.
SOURCES = [
    dict(id="brampton_preconsultation", city="Brampton", stage="PRE_CONSULTATION",
         url=BRAMPTON+"10", id_fields=("FILE_NUMBER",),
         date_fields=("DATE_RECEIVED",),
         desc_fields=("PROPOSAL_DESCRIPTION", "DESCRIPTION", "APPLICATION_TITLE"),
         entity_fields=("APPLICANT_COMPANY", "AGENT_COMPANY"),
         address_fields=("LOCATION",), status_fields=("STATUS",)),
    dict(id="brampton_rezoning_opa", city="Brampton", stage="REZONING_OPA",
         url=BRAMPTON+"9", id_fields=("FILE_NUMBER",),
         date_fields=("DATE_RECEIVED",),
         desc_fields=("PROPOSAL_DESCRIPTION", "DESCRIPTION", "APPLICATION_TITLE"),
         entity_fields=("APPLICANT_COMPANY", "AGENT_COMPANY"),
         address_fields=("LOCATION",), status_fields=("STATUS",)),
    dict(id="brampton_site_plans", city="Brampton", stage="SITE_PLAN",
         url=BRAMPTON+"11", id_fields=("FILE_NUMBER",),
         date_fields=("DATE_RECEIVED",),
         desc_fields=("PROPOSAL_DESCRIPTION", "DESCRIPTION", "APPLICATION_TITLE"),
         entity_fields=("APPLICANT_COMPANY", "AGENT_COMPANY"),
         address_fields=("LOCATION",), status_fields=("STATUS",)),
    dict(id="mississauga_site_plans", city="Mississauga", stage="SITE_PLAN",
         url=MISSAUGA+"Site_Plan_Applications/FeatureServer/0",
         id_fields=("APP_FILE_NO", "PLNG_APP_ID"),
         date_fields=("APPLICATION_DATE",),
         desc_fields=("DESCRIPTION", "TYPE_DESC", "CATEGORY_DESC"),
         entity_fields=("APPLICANT",), address_fields=("SITE_ADDRESS", "GENERAL_LOCATION"),
         status_fields=("SIMPLE_STATUS",)),
    dict(id="mississauga_rezonings", city="Mississauga", stage="REZONING",
         url=MISSAUGA+"Rezoning_Applications/FeatureServer/0",
         id_fields=("APP_FILE_NO", "PLNG_APP_ID"),
         date_fields=("APPLICATION_DATE",),
         desc_fields=("DESCRIPTION", "TYPE_DESC", "CATEGORY_DESC"),
         entity_fields=("APPLICANT",), address_fields=("SITE_ADDRESS", "GENERAL_LOCATION"),
         status_fields=("SIMPLE_STATUS",)),
    dict(id="york_region_development", city="York Region (Vaughan included)", stage="PLANNING",
         url=YORK, id_fields=("APPL_GISID",),
         date_fields=("DATE_RECVD",),
         desc_fields=("APPL_DESC", "APPL_TYPE", "APPL_SUBTYPE"),
         entity_fields=("APPL_NAME",), address_fields=("ADDRESS",),
         status_fields=("APPL_STATUS", "APPL_STAGE")),
    dict(id="toronto_development", city="Toronto", stage="PLANNING",
         url=TORONTO, id_fields=("APPLICATION_NUMBER",),
         date_fields=("INDATE", "SUBMIT_DATE"),
         desc_fields=("FOLDERDESCRIPTION", "APPLICATION_TYPE", "FOLDERTYPE_DESC"),
         entity_fields=(), address_fields=("FULL_ADDRESS",),
         status_fields=("STATUS_DESC", "LATEST_MILESTONE")),
]

COMMERCIAL_TERMS = (
    "industrial", "warehouse", "manufactur", "commercial", "retail", "office",
    "hotel", "hospitality", "data centre", "data center", "logistic", "factory",
    "distribution", "employment", "business park", "institutional", "restaurant",
    "laboratory", "industrial expansion", "storage facility", "medical clinic",
)
RESIDENTIAL_TERMS = (
    "single detached", "single family", "residential", "townhouse", "condominium",
    "apartment", "dwelling", "semi-detached", "triplex", "duplex",
)
COLUMNS = (
    "observed_at", "source_id", "city", "stage", "change_type", "record_scope",
    "application_id", "feature_id", "source_application_date", "description",
    "location", "published_company_unverified_role", "status", "commercial_signal",
    "source_url", "qualification",
)
STATUS_COLUMNS = ("source_id", "city", "status", "fetched", "new", "updated", "baseline", "error")


def get_json(session, url, params, *, method="GET", phase="GIS query"):
    """Include the request stage in errors; never silently accept HTML as JSON."""
    try:
        if method == "POST":
            response = session.post(url, data=params, timeout=(10, 50))
        else:
            response = session.get(url, params=params, timeout=(10, 50))
        response.raise_for_status()
    except requests.RequestException as exc:
        code = getattr(locals().get("response"), "status_code", "unknown")
        raise RuntimeError(f"{phase}: HTTP/network error (status {code}): {type(exc).__name__}") from exc
    try:
        result = response.json()
    except ValueError as exc:
        content_type = str(getattr(response, "headers", {}).get("content-type", "unknown"))
        raise RuntimeError(f"{phase}: non-JSON response (HTTP {getattr(response, 'status_code', 'unknown')}, type {content_type})") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{phase}: GIS service returned non-object JSON")
    if "error" in result:
        raise RuntimeError(f"{phase}: official GIS error: " + str(result["error"])[:120])
    return result


def fetch_layer(session, source, maximum=25000):
    """Fetch complete feature-ID snapshots; use small batches if a large request fails."""
    sid = source["id"]
    meta = get_json(session, source["url"], {"f": "json"}, phase=sid+" metadata")
    fields = {str(f.get("name", "")).upper() for f in meta.get("fields", [])}
    oid = str(meta.get("objectIdField") or "")
    if not oid or oid.upper() not in fields:
        raise RuntimeError(f"{sid}: GIS layer lacks a documented object-ID field")
    query = source["url"] + "/query"
    params = {"f": "json", "where": "1=1", "returnIdsOnly": "true"}
    try:
        result = get_json(session, query, params, phase=sid+" ID inventory GET")
    except RuntimeError as first_error:
        # Some municipal GIS gateways deliver HTML/blocked responses for large GETs.
        try:
            result = get_json(session, query, params, method="POST",
                              phase=sid+" ID inventory POST")
        except (RuntimeError, AttributeError) as second_error:
            raise RuntimeError(f"{sid}: ID inventory failed by GET ({first_error}) "
                               f"and POST ({second_error})") from second_error
    ids = result.get("objectIds")
    if not isinstance(ids, list):
        raise RuntimeError(f"{sid}: GIS ID inventory unavailable")
    if not ids or len(ids) > maximum or len(set(ids)) != len(ids):
        raise RuntimeError(f"{sid}: empty, oversized, or duplicate GIS ID inventory")
    rows = []

    def fetch_batch(batch, label):
        params = {"f": "json", "objectIds": ",".join(map(str, batch)),
                  "outFields": "*", "returnGeometry": "false"}
        packet = get_json(session, query, params, phase=sid+" "+label)
        features = packet.get("features")
        if not isinstance(features, list) or packet.get("exceededTransferLimit"):
            raise RuntimeError(f"{sid} {label}: incomplete GIS feature batch")
        return features

    for offset in range(0, len(ids), 250):
        batch = ids[offset:offset+250]
        try:
            features = fetch_batch(batch, f"batch {offset} ({len(batch)} IDs)")
        except RuntimeError:
            # If a municipality rejects a long GET/large response, retry at 20 IDs.
            # Retried results are still checked against the entire official ID list.
            features = []
            for mini in range(0, len(batch), 20):
                sub_batch = batch[mini:mini+20]
                features.extend(fetch_batch(sub_batch, f"small batch {offset+mini}"))
        for feature in features:
            values = feature.get("attributes")
            if not isinstance(values, dict):
                raise RuntimeError(f"{sid}: invalid GIS attributes at batch {offset}")
            rows.append({str(k).upper(): v for k, v in values.items()})
    returned = [row.get(oid.upper()) for row in rows]
    if len(returned) != len(ids) or set(returned) != set(ids):
        raise RuntimeError(f"{sid}: GIS snapshot incomplete or changed mid-fetch")
    return rows, oid.upper()


def first(row, fields):
    for field in fields:
        value = row.get(field.upper())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def classify(description):
    text = description.casefold()
    commercial = any(term in text for term in COMMERCIAL_TERMS)
    residential = any(term in text for term in RESIDENTIAL_TERMS)
    if commercial and not residential:
        return "POSSIBLE_COMMERCIAL"
    if commercial and residential:
        return "MIXED_USE_REVIEW"
    if residential:
        return "RESIDENTIAL_LIKELY"
    return "USE_UNKNOWN"


def summarize(source, row, oid, id_counts, observed_at):
    app_id = first(row, source["id_fields"])
    feature_id = str(row[oid])
    scope = "APPLICATION_ID" if app_id and id_counts[app_id] == 1 else "FEATURE_ONLY"
    key = ("APP:" + app_id) if scope == "APPLICATION_ID" else ("OID:" + feature_id)
    description = " | ".join(dict.fromkeys(
        str(row.get(field.upper()) or "").strip()
        for field in source["desc_fields"]
        if str(row.get(field.upper()) or "").strip()
    ))[:1200]
    date, date_field = get_source_date(row, source["date_fields"])
    company_field = next((f for f in source["entity_fields"] if first(row, (f,))), "")
    role = ("PUBLISHED_APPLICANT_NOT_BUYER" if company_field in ("APPLICANT", "APPLICANT_COMPANY")
            else "PUBLISHED_AGENT_NOT_BUYER" if company_field == "AGENT_COMPANY"
            else "PUBLISHED_APPLICATION_NAME_NOT_BUYER" if company_field else "COMPANY_UNKNOWN")
    return dict(
        quality_version=QUALITY_VERSION, source_date_basis=date_field,
        company_role=role,
        source_id=source["id"], city=source["city"], stage=source["stage"],
        record_key=key, record_scope=scope,
        application_id=app_id, feature_id=feature_id,
        source_application_date=date,
        description=description, location=first(row, source["address_fields"])[:250],
        published_company_unverified_role=first(row, source["entity_fields"])[:180],
        status=first(row, source["status_fields"])[:180],
        commercial_signal=quality_classify(description, row), source_url=source["url"],
        qualification="PUBLIC_PLANNING_RECORD_REVIEW_ONLY",
        observed_at=observed_at,
    )


def prepare_rows(source, rows, oid, observed_at):
    counts = Counter(first(row, source["id_fields"]) for row in rows)
    records = [summarize(source, row, oid, counts, observed_at) for row in rows]
    if len({r["record_key"] for r in records}) != len(records):
        raise RuntimeError("Ambiguous application/feature IDs; refusing partial update")
    return records


def setup(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS observations (
        source_id TEXT NOT NULL, record_key TEXT NOT NULL,
        first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
        digest TEXT NOT NULL, content TEXT NOT NULL,
        PRIMARY KEY(source_id, record_key)
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL, source_id TEXT NOT NULL,
        record_key TEXT NOT NULL, change_type TEXT NOT NULL, content TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS source_runs (
        id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL, source_id TEXT NOT NULL,
        status TEXT NOT NULL, fetched INTEGER NOT NULL, new_count INTEGER NOT NULL,
        updated_count INTEGER NOT NULL, baseline INTEGER NOT NULL, error TEXT
    );
    """)


def digest(item):
    payload = {key: value for key, value in item.items() if key != "observed_at"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def save_records(db, source, records, observed_at):
    """One atomic source update; initial snapshot never generates fresh alerts."""
    sid = source["id"]
    previous = {row[0]: (row[1], row[2]) for row in db.execute(
        "SELECT record_key, digest, content FROM observations WHERE source_id=?", (sid,)
    )}
    baseline = not previous
    new_count = updated = 0
    with db:
        for item in records:
            key = item["record_key"]
            data = json.dumps(item, ensure_ascii=False, sort_keys=True)
            hash_value = digest(item)
            old = previous.get(key)
            old_hash = old[0] if old else None
            # V1 had malformed dates. The first V2 refetch upgrades quality
            # without manufacturing source-change alerts or losing first_seen.
            legacy_migration = False
            if old is not None:
                try:
                    legacy_migration = json.loads(old[1]).get("quality_version") != QUALITY_VERSION
                except (ValueError, TypeError, AttributeError):
                    legacy_migration = True
            if old is None:
                new_count += 1
            elif old_hash != hash_value and not legacy_migration:
                updated += 1
            db.execute("""INSERT INTO observations VALUES(?,?,?,?,?,?)
                ON CONFLICT(source_id,record_key) DO UPDATE SET
                last_seen=excluded.last_seen,digest=excluded.digest,content=excluded.content
                """, (sid, key, observed_at, observed_at, hash_value, data))
            if not baseline and (old is None or (old_hash != hash_value and not legacy_migration)):
                db.execute("INSERT INTO events(observed_at,source_id,record_key,change_type,content) VALUES(?,?,?,?,?)",
                           (observed_at,sid,key,"NEW" if prior is None else "UPDATED",data))
        db.execute("INSERT INTO source_runs(observed_at,source_id,status,fetched,new_count,updated_count,baseline,error) VALUES(?,?,?,?,?,?,?,?)",
                   (observed_at,sid,"SUCCESS",len(records),new_count,updated,int(baseline),""))
    return dict(source_id=sid,city=source["city"],status="SUCCESS",fetched=len(records),
                new=new_count,updated=updated,baseline="YES" if baseline else "NO",error="")


def export_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def run(data_dir, output_dir=None, ids=None, session=None, now=None):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path(output_dir or data_dir / "GTA_RADAR_RESULTS")
    output_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(data_dir / "early_signals_review.sqlite")
    setup(db)
    session = session or requests.Session()
    session.headers.update({"User-Agent": "GTACommercialRadar-EarlySignals/0.1 (review only)"})
    stamp = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    statuses = []
    selection = [source for source in SOURCES if not ids or source["id"] in ids]
    if ids and len(selection) != len(ids):
        raise ValueError("Unknown source ID(s): " + ", ".join(sorted(set(ids)-
                         {item["id"] for item in SOURCES})))
    try:
        for source in selection:
            try:
                raw, oid = fetch_layer(session, source)
                records = prepare_rows(source, raw, oid, stamp)
                status = save_records(db, source, records, stamp)
            except (requests.RequestException, ValueError, TypeError, KeyError,
                    RuntimeError, sqlite3.DatabaseError) as exc:
                db.rollback()
                status = dict(source_id=source["id"],city=source["city"],
                              status="FAILED",fetched=0,new=0,updated=0,
                              baseline="NO",error=type(exc).__name__+": "+str(exc)[:220])
            statuses.append(status)
            print(status["source_id"], status["status"], "records=", status["fetched"],
                  "changes=", status["new"]+status["updated"], flush=True)

        changed = []
        for (event_time, event_type, content) in db.execute(
                "SELECT observed_at,change_type,content FROM events WHERE observed_at=? ORDER BY id",
                (stamp,)):
            item = json.loads(content)
            item.update(observed_at=event_time, change_type=event_type)
            changed.append(item)

        # Keep unknown-use events in an explicit review file; never label sale-ready.
        export_csv(output_dir / "EARLY_SIGNALS_CHANGES_REVIEW_ONLY.csv", COLUMNS, changed)
        export_csv(output_dir / "EARLY_SIGNALS_SOURCES_STATUS.csv", STATUS_COLUMNS, statuses)
        quality = export_project_reports(db, output_dir)
        print("Quality review candidates:", quality["review_candidates"],
              "| Source date is NOT publication date")
        print("Review-only changes:", len(changed),
              "| No baseline records treated as new leads | No DeepSeek used")
        return 1 if any(s["status"]=="FAILED" for s in statuses) else 0
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Free GTA planning pre-permit pilot; no paid AI")
    parser.add_argument("--data-dir", default=str(ROOT/"data"))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--source", action="append", default=[])
    args = parser.parse_args(argv)
    return run(args.data_dir,args.output_dir,args.source or None)


if __name__ == "__main__":
    raise SystemExit(main())
