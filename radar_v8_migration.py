"""V8 SQLite history adapter and non-destructive active database adoption.

V8 uses records_current / record_versions / changes / runs, unlike the early
pilot schema. Read sources with SQLite URI mode=ro, never rewrite first-seen
history or invent NEW events from baseline imports.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path


V8_CURRENT = ("source_id", "record_key", "first_seen_at", "last_seen_at",
              "source_date", "active", "normalized_json")
V8_VERSIONS = ("source_id", "record_key", "observed_at", "payload_json")
V8_CHANGES = ("source_id", "record_key", "observed_at", "change_type", "normalized_json")


def supported(db, has_fields):
    return has_fields(db, "records_current", V8_CURRENT) and (
        has_fields(db, "record_versions", V8_VERSIONS)
        and has_fields(db, "changes", V8_CHANGES))


def import_v8(master, source, file, seen_at, counts, has_fields, payload):
    """Import V8 current, historical versions, change events and per-source runs."""
    if not supported(source, has_fields):
        return False
    # Event schema and underlying project data remain separate. Inactive is
    # preserved; a removed permit is NOT presented as an active opportunity.
    for sid, rid, first, last, source_date, active, body in source.execute(
            "SELECT source_id,record_key,first_seen_at,last_seen_at,"
            "source_date,active,normalized_json FROM records_current"):
        if not sid or not rid:
            continue
        item, packed, digest = payload(body)
        item["_radar_v8_active"] = bool(active)
        item["_radar_v8_record_key"] = str(rid)
        # Preserve display provenance and activity, not as a new public change.
        packed = json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(packed.encode("utf-8")).hexdigest()
        sid, rid = str(sid), str(rid)
        prior = master.execute(
            "SELECT first_seen_at,last_seen_at FROM records "
            "WHERE source_id=? AND record_id=?", (sid, rid)).fetchone()
        if prior is None:
            master.execute(
                "INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)",
                (sid, rid, first, last, source_date, packed, digest, seen_at, str(file)))
            counts["new_records"] += 1
        elif (last or "") >= (prior[1] or ""):
            master.execute(
                "UPDATE records SET first_seen_at=?,last_seen_at=?,source_date=?,"
                "payload_json=?,payload_hash=?,last_imported_at=?,provenance=? "
                "WHERE source_id=? AND record_id=?",
                (min((x for x in (prior[0],first) if x),default=None),
                 last,source_date,packed,digest,seen_at,str(file),sid,rid))
        # Historical content itself belongs in record_versions (below), not
        # a second synthetic event that falsely claims a fresh project change.
    for sid, rid, observed, body in source.execute(
            "SELECT source_id,record_key,observed_at,payload_json "
            "FROM record_versions ORDER BY version_id"):
        if not sid or not rid:
            continue
        _, packed, digest = payload(body)
        inserted = master.execute(
            "INSERT OR IGNORE INTO record_versions "
            "(source_id,record_id,payload_hash,payload_json,observed_at,provenance)"
            " VALUES(?,?,?,?,?,?)",
            (str(sid),str(rid),digest,packed,observed or seen_at,str(file)))
        counts["added_versions"] += inserted.rowcount
    for sid, rid, observed, kind, body in source.execute(
            "SELECT source_id,record_key,observed_at,change_type,normalized_json "
            "FROM changes ORDER BY change_id"):
        if not sid or not rid or not observed:
            continue
        _, packed, digest = payload(body)
        key = hashlib.sha256(json.dumps(
            (str(sid),str(rid),str(observed),str(kind),digest),
            separators=(",", ":")).encode("utf-8")).hexdigest()
        inserted = master.execute(
            "INSERT OR IGNORE INTO historical_events VALUES(?,?,?,?,?,?,?)",
            (key,str(sid),str(rid),str(kind),str(observed),str(file),packed))
        counts["added_events"] += inserted.rowcount
    if has_fields(source,"runs",("run_id","source_id","started_at","finished_at",
                                  "success","baseline","record_count","new_count",
                                  "updated_count","removed_count","error","metadata_json")):
        for row in source.execute(
                "SELECT run_id,source_id,started_at,finished_at,success,baseline,"
                "record_count,new_count,updated_count,removed_count,"
                "latest_source_date,error,metadata_json FROM runs ORDER BY run_id"):
            master.execute(
                "INSERT OR IGNORE INTO source_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(file),*row))
            counts["source_runs_imported"] += master.execute("SELECT changes()").fetchone()[0]
    return True


def adopt_database(home, original, has_fields):
    """Copy a consistent V8 SQLite snapshot once; never overwrite an existing DB."""
    home=Path(home).expanduser().resolve()
    original=Path(original).expanduser().resolve()
    dest=home/"Data"/"radar.sqlite"
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not original.is_file():
        raise FileNotFoundError("Existing V8 radar.sqlite not found")
    if original==dest:
        raise ValueError("V8 source and active destination are the same")
    if dest.exists():
        raise FileExistsError("Permanent V8 database already exists; replacement refused")
    staging=dest.with_name(dest.name+".adopting")
    if staging.exists():
        raise FileExistsError("Previous unfinished adoption must be inspected")
    try:
        with closing(sqlite3.connect(original.as_uri()+"?mode=ro",uri=True)) as source:
            if not supported(source,has_fields):
                raise ValueError("Not a recognized V8 collector database")
            with closing(sqlite3.connect(staging)) as target:
                source.backup(target, pages=512, sleep=0.1)
                if target.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                    raise RuntimeError("Backup failed SQLite validation")
                target.commit()
        # On Windows, a race could replace a pre-existing path; prevent clobber.
        if dest.exists():
            raise FileExistsError("Another process adopted V8 simultaneously")
        os.replace(staging,dest)
        return str(dest)
    finally:
        staging.unlink(missing_ok=True)
