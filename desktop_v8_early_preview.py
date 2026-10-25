"""Safe first V8 desktop run: clone established SQLite histories once.

The preview runs one real V8 collection pipeline on its *own* persistent
working copy, with zero DeepSeek calls and no changes to scheduled tasks.
The original workspace/data and results remain untouched.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from v6_daily_pipeline import find_workspace, choose_database

PREVIEW_DIR = "GTA_RADAR_V8_EARLY_PREVIEW"
SOURCE_EXTENSIONS = {".sqlite", ".sqlite3", ".db"}


def snapshot_once(source, destination):
    """SQLite online backup, crash-safe replacement, preserve preview history."""
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        return False
    if source == destination:
        raise ValueError("Preview must never write to the established source DB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_name(destination.name + ".copying")
    if pending.exists():
        raise RuntimeError(f"Interrupted prior snapshot: {pending} (not overwriting)")
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=15) as original:
            with sqlite3.connect(pending, timeout=15) as isolated:
                original.backup(isolated, pages=2048, sleep=0.1)
                if isolated.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError("Isolated SQLite backup failed validation")
        pending.replace(destination)
        return True
    except BaseException:
        pending.unlink(missing_ok=True)
        raise


def prepare(workspace=None, original_db=None):
    home = Path(workspace).resolve() if workspace else find_workspace()
    main_db = Path(original_db).resolve() if original_db else choose_database(home)
    if not main_db.is_file():
        raise FileNotFoundError(f"Established database not found: {main_db}")
    root = home / PREVIEW_DIR
    data = root / "data"
    results = root / "GTA_RADAR_RESULTS"
    manifest = root / "PREVIEW_SOURCE.json"
    data.mkdir(parents=True, exist_ok=True)
    # All original pilot SQLite baselines in the same data directory are copied,
    # allowing true first-seen comparisons without touching original history.
    files = sorted(p for p in main_db.parent.iterdir()
                   if p.is_file() and p.suffix.lower() in SOURCE_EXTENSIONS)
    if main_db not in files:
        files.append(main_db)
    seen_targets = set()
    for item in files:
        dest_name = "radar.sqlite" if item.resolve() == main_db else item.name
        if dest_name in seen_targets:
            raise RuntimeError("Conflicting pilot SQLite filenames; safe preview aborted")
        seen_targets.add(dest_name)
        snapshot_once(item, data / dest_name)
    if not (data / "radar.sqlite").exists():
        raise RuntimeError("Isolated Radar database missing after backup")
    if not manifest.exists():
        manifest.write_text(json.dumps({
            "source_workspace": str(home),
            "source_database": str(main_db),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "persistent isolated collection pilot, no paid AI, no scheduler",
        }, indent=2), encoding="utf-8")
    results.mkdir(parents=True, exist_ok=True)
    return home, data / "radar.sqlite", results


def run():
    home, database, results = prepare()
    script = Path(__file__).resolve().with_name("v6_daily_pipeline.py")
    cmd = [sys.executable, str(script), "--workspace", str(home),
           "--database", str(database), "--results-dir", str(results),
           "--no-ai", "--no-schedule", "--unattended"]
    print("GTA Radar V8: early source desktop validation (NO DEEPSEEK)", flush=True)
    print("Original database preserved; collecting into:", database, flush=True)
    print("Pilot output folder:", results, flush=True)
    done = subprocess.run(cmd, check=False)
    report = results / "GTA_RADAR_V6_DASHBOARD.html"
    if report.exists():
        print("One dashboard:", report, flush=True)
        try:
            if os.name == "nt":
                os.startfile(str(report))
            else:
                webbrowser.open(report.as_uri())
        except OSError as error:
            print("Open the dashboard manually:", error, flush=True)
    print("Pre-permit signals:", results / "GTA_RADAR_EARLY_CUES_REVIEW.csv",flush=True)
    print("All 53 configured/pilot source definitions:",
          results / "GTA_RADAR_ALL_SOURCE_STATUS.csv",flush=True)
    return done.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print("Safe preview stopped:", type(exc).__name__, str(exc)[:350],
              flush=True)
        raise SystemExit(1)
