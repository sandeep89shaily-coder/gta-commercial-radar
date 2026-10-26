"""Persistent, non-destructive workspace for GTA Radar early-source intelligence.

One data directory, one normalized evidence database and one results directory.
Importing other installations reads their SQLite data in read-only mode; it
never resets their baselines, modifies schedules, or invokes paid AI.

This module is a foundation, NOT a replacement for project matching,
commercial qualification, or buyer/procurement verification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path

SCHEMA_VERSION = 1
DB_NAME = "radar_master.sqlite"
DATA_DIRS = ("Workspace/Data", "data", "Data")
RESULT_DIRS = ("Workspace/Results", "GTA_RADAR_RESULTS", "Results")
SNAPSHOT_EXTENSIONS = (".sqlite", ".db")
HEALTH_FIELDS = ("source_id", "runner", "status", "execution_status",
                 "state", "error", "warning", "fetched", "new", "updated")


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def home_path(value=None):
    if value:
        return Path(value).expanduser().resolve()
    custom = os.getenv("GTA_RADAR_HOME", "").strip()
    return (Path(custom) if custom else Path.home() / "Documents" / "GTA_Radar").expanduser().resolve()


def setup(home):
    home = Path(home).resolve()
    for folder in ("Data", "Results", "Logs"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    dbfile = home / "Data" / DB_NAME
    db = sqlite3.connect(dbfile)
    try:
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(
              key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records(
              source_id TEXT NOT NULL, record_id TEXT NOT NULL,
              first_seen_at TEXT, last_seen_at TEXT, source_date TEXT,
              payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
              last_imported_at TEXT NOT NULL, provenance TEXT NOT NULL,
              PRIMARY KEY(source_id, record_id)
            );
            CREATE TABLE IF NOT EXISTS record_versions(
              source_id TEXT NOT NULL, record_id TEXT NOT NULL,
              payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
              observed_at TEXT NOT NULL, provenance TEXT NOT NULL,
              PRIMARY KEY(source_id,record_id,payload_hash)
            );
            CREATE TABLE IF NOT EXISTS historical_events(
              event_key TEXT PRIMARY KEY, source_id TEXT NOT NULL,
              record_id TEXT NOT NULL, event_type TEXT NOT NULL,
              event_at TEXT NOT NULL, provenance TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS import_runs(
              import_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
              completed_at TEXT, roots_json TEXT NOT NULL,
              new_records INTEGER NOT NULL DEFAULT 0,
              added_versions INTEGER NOT NULL DEFAULT 0,
              added_events INTEGER NOT NULL DEFAULT 0,
              read_errors_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS feed_health(
              import_id TEXT NOT NULL, source_id TEXT NOT NULL,
              source_report TEXT NOT NULL, reported_status TEXT NOT NULL,
              detail_json TEXT NOT NULL,
              PRIMARY KEY(import_id,source_id,source_report)
            );
            CREATE INDEX IF NOT EXISTS idx_records_source_date
              ON records(source_id,source_date);
            CREATE INDEX IF NOT EXISTS idx_events_date
              ON historical_events(event_at,source_id);
        """)
        row = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if row and int(row[0]) != SCHEMA_VERSION:
            raise RuntimeError("Unsupported Radar master schema; preserve data and upgrade explicitly")
        db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES(?,?)",
                   ("schema_version", str(SCHEMA_VERSION)))
        db.commit()
    finally:
        db.close()
    return dbfile


def _candidate_dirs(root, names):
    root = Path(root).resolve()
    found = []
    for candidate in (root, *(root / name for name in names)):
        if candidate.is_dir() and candidate not in found:
            found.append(candidate)
    return found


def source_databases(root, master):
    found = set()
    for folder in _candidate_dirs(root, DATA_DIRS):
        for path in folder.iterdir():
            if (path.is_file() and path.suffix.lower() in SNAPSHOT_EXTENSIONS
                    and path.resolve() != master.resolve()):
                found.add(path.resolve())
    return sorted(found)


def _read_only(path):
    # URI mode=ro guarantees an import never modifies any legacy database.
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def _has_fields(db, table, names):
    allowed = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone()
    if not allowed:
        return False
    cols = {r[1] for r in db.execute('PRAGMA table_info("' + table + '")')}
    return set(names).issubset(cols)


def _payload(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    item = json.loads(raw)
    if not isinstance(item, dict):
        raise ValueError("Snapshot content must be an object")
    packed = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return item, packed, hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _import_database(master, file, seen_at, counts):
    source = _read_only(file)
    try:
        has_snapshots = _has_fields(
            source, "snapshots",
            ("source_id", "record_id", "first_seen_at", "last_seen_at", "content"))
        has_changes = _has_fields(
            source, "changes",
            ("source_id", "record_id", "observed_at", "change_type", "content"))
        if not (has_snapshots or has_changes):
            return False
        if has_snapshots:
            rows = source.execute(
                "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots")
            for sid, rid, first, last, body in rows:
                if not sid or not rid:
                    continue
                item, packed, digest = _payload(body)
                sid, rid = str(sid), str(rid)
                inserted = master.execute(
                    "INSERT OR IGNORE INTO record_versions "
                    "(source_id,record_id,payload_hash,payload_json,observed_at,provenance)"
                    " VALUES (?,?,?,?,?,?)",
                    (sid, rid, digest, packed, last or first or seen_at, str(file)))
                counts["added_versions"] += inserted.rowcount
                date = str(item.get("source_date") or item.get("published_date") or "")
                prev = master.execute(
                    "SELECT last_seen_at FROM records WHERE source_id=? AND record_id=?",
                    (sid, rid)).fetchone()
                if prev is None:
                    master.execute(
                        "INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)",
                        (sid, rid, first, last, date, packed, digest, seen_at, str(file)))
                    counts["new_records"] += 1
                elif (last or "") >= (prev[0] or ""):
                    master.execute(
                        "UPDATE records SET first_seen_at=COALESCE(first_seen_at,?),"
                        "last_seen_at=?,source_date=?,payload_json=?,payload_hash=?,"
                        "last_imported_at=?,provenance=? WHERE source_id=? AND record_id=?",
                        (first, last, date, packed, digest, seen_at, str(file), sid, rid))
        if has_changes:
            for sid, rid, observed, kind, body in source.execute(
                    "SELECT source_id,record_id,observed_at,change_type,content FROM changes"):
                if not sid or not rid or not observed:
                    continue
                _, packed, digest = _payload(body)
                ident = json.dumps((str(sid), str(rid), str(observed), str(kind), digest))
                key = hashlib.sha256(ident.encode("utf-8")).hexdigest()
                inserted = master.execute(
                    "INSERT OR IGNORE INTO historical_events VALUES(?,?,?,?,?,?,?)",
                    (key, str(sid), str(rid), str(kind), str(observed),
                     str(file), packed))
                counts["added_events"] += inserted.rowcount
        return True
    finally:
        source.close()


def _health_files(root):
    found = set()
    for folder in _candidate_dirs(root, RESULT_DIRS):
        priority = folder / "GTA_RADAR_EARLY_SOURCES.csv"
        if priority.is_file():
            found.add(priority.resolve())
        else:
            found.update(p.resolve() for p in folder.glob("*SOURCE_STATUS.csv"))
    return sorted(found)


def _import_health(db, root, run_id):
    count = 0
    for report in _health_files(root):
        with report.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                sid = row.get("source_id") or ""
                if not sid:
                    continue
                status = (row.get("status") or row.get("execution_status")
                          or row.get("state") or "UNREPORTED")
                db.execute(
                    "INSERT OR REPLACE INTO feed_health VALUES(?,?,?,?,?)",
                    (run_id, sid, str(report), status,
                     json.dumps(row, sort_keys=True, ensure_ascii=False)))
                count += 1
    return count


def import_history(home, roots):
    """Read historical pilot snapshots and source status without changing sources.

    This is an idempotent IMPORT, never a new-public-event detector.
    No unknown legacy SQLite schema is silently treated as a successful feed.
    """
    root = Path(home).resolve()
    master_file = setup(root)
    checked = [Path(p).expanduser().resolve() for p in roots]
    run_id = uuid.uuid4().hex
    started = utcnow()
    counts = {"new_records": 0, "added_versions": 0,
              "added_events": 0, "source_status_rows": 0,
              "source_databases_read": 0, "unsupported_databases": 0,
              "read_errors": []}
    with closing(sqlite3.connect(master_file)) as db:
        db.execute(
            "INSERT INTO import_runs(import_id,started_at,roots_json) VALUES(?,?,?)",
            (run_id, started, json.dumps([str(x) for x in checked])))
        for folder in checked:
            if not folder.is_dir():
                counts["read_errors"].append("Missing folder: " + str(folder))
                continue
            for filename in source_databases(folder, master_file):
                # Savepoint ensures a corrupt source does not partially import.
                db.execute("SAVEPOINT source_import")
                before = {name: counts[name] for name in
                          ("new_records", "added_versions", "added_events")}
                try:
                    supported = _import_database(db, filename, started, counts)
                    if supported:
                        counts["source_databases_read"] += 1
                    else:
                        counts["unsupported_databases"] += 1
                    db.execute("RELEASE source_import")
                except (sqlite3.Error, ValueError, UnicodeError, TypeError) as exc:
                    db.execute("ROLLBACK TO source_import")
                    db.execute("RELEASE source_import")
                    counts.update(before)  # Rolled-back work is not counted.
                    counts["read_errors"].append(filename.name + ": "
                                                 + type(exc).__name__)
            try:
                counts["source_status_rows"] += _import_health(db, folder, run_id)
            except (csv.Error, UnicodeError, OSError) as exc:
                counts["read_errors"].append("Health report: " + type(exc).__name__)
        db.execute(
            "UPDATE import_runs SET completed_at=?,new_records=?,"
            "added_versions=?,added_events=?,read_errors_json=? WHERE import_id=?",
            (utcnow(), counts["new_records"], counts["added_versions"],
             counts["added_events"], json.dumps(counts["read_errors"]), run_id))
        db.commit()
    counts["run_id"] = run_id
    return counts


def status(home):
    dbfile = setup(home)
    with closing(sqlite3.connect(dbfile)) as db:
        def one(sql):
            return db.execute(sql).fetchone()[0]
        result = {
            "workspace": str(Path(home).resolve()),
            "records": one("SELECT COUNT(*) FROM records"),
            "distinct_sources_with_records": one("SELECT COUNT(DISTINCT source_id) FROM records"),
            "record_versions": one("SELECT COUNT(*) FROM record_versions"),
            "historical_events": one("SELECT COUNT(*) FROM historical_events"),
            "imports": one("SELECT COUNT(*) FROM import_runs"),
            "last_import": db.execute(
                "SELECT completed_at FROM import_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone(),
        }
        result["last_import"] = result["last_import"][0] if result["last_import"] else None
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", help="Persistent Radar home (or GTA_RADAR_HOME)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create permanent folders and control database")
    imported = sub.add_parser("import", help="Import old evidence read-only")
    imported.add_argument("folders", nargs="+", help="Existing Radar folder(s)")
    sub.add_parser("status", help="Report actual normalized record/history counts")
    sub.add_parser("collect", help="Run existing early collectors without paid AI and import")
    args = parser.parse_args(argv)
    home = home_path(args.home)
    if args.command == "init":
        result = {"database": str(setup(home)), "mode": "NO_PAID_AI"}
    elif args.command == "import":
        result = import_history(home, args.folders)
    elif args.command == "status":
        result = status(home)
    else:
        # Use the existing collector pipeline without replacing its snapshot DBs.
        from early_investment_radar import run
        state = run(home / "Data", home / "Results", paid=False)
        imported = import_history(home, [home])
        result = {"collection_status": state.get("status"),
                  "collection_steps": state.get("steps", []),
                  "import": imported, "mode": "NO_PAID_AI"}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result.get("read_errors") else 0


if __name__ == "__main__":
    sys.exit(main())
