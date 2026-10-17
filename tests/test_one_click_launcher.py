"""End-to-end test of the self-contained one-click review launcher."""
import csv
import datetime as dt
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / "START_GTA_RADAR_ONE_CLICK.bat"

class OneClickSmoke(unittest.TestCase):
    def test_missing_export_readonly_and_project_grouping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "new data"
            data = root / "GTA_RADAR_DAILY_48H" / "data"
            data.mkdir(parents=True)
            dbfile = data / "radar.sqlite"
            today = dt.date.today().isoformat()
            with sqlite3.connect(dbfile) as db:
                db.execute("CREATE TABLE records_current (source_id TEXT,record_key TEXT,source_date TEXT,normalized_json TEXT,active INTEGER,PRIMARY KEY(source_id,record_key))")
                db.execute("CREATE TABLE changes (source_id TEXT,record_key TEXT,observed_at TEXT,change_type TEXT,normalized_json TEXT)")
                def record(key,description):
                    payload = {"description":description,"address":"100 Fictional Rd","region":"Toronto"}
                    db.execute("INSERT INTO records_current VALUES (?,?,?,?,1)",("toronto_active_building_permits",key,today,json.dumps(payload)))
                    return payload
                main = record("26 123456 BLD | 01","Industrial warehouse new construction HVAC")
                record("26 123456 PLB | 01","Industrial warehouse plumbing")
                record("26 999999 BLD | 01","Single detached dwelling basement apartment")
                db.execute("INSERT INTO changes VALUES (?,?,?,?,?)",("toronto_active_building_permits","26 123456 BLD | 01",today+"T09:00:00","UPDATED",json.dumps(main)))
                db.commit()
            db.close()  # sqlite3 context managers do not close connections on Windows.
            original_hash = hashlib.sha256(dbfile.read_bytes()).digest()
            execution = subprocess.run([sys.executable,"-x",str(LAUNCHER),"--root",str(root),"--no-open"],capture_output=True,text=True,timeout=40)
            self.assertEqual(execution.returncode,0,execution.stdout+"\n"+execution.stderr)
            self.assertEqual(hashlib.sha256(dbfile.read_bytes()).digest(),original_hash)
            self.assertFalse((data / "opportunities_ALL_REVIEW_ONLY.csv").exists())
            results = root / "GTA_RADAR_RESULTS"
            self.assertIn("OFFLINE, UNVERIFIED REVIEW",(results / "commercial_candidates_v4.html").read_text(encoding="utf-8"))
            with (results / "CANDIDATES_V4_ALL_REVIEW_ONLY.csv").open(encoding="utf-8-sig",newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["permit_count"],"2")
            self.assertEqual(rows[0]["lane"],"SOURCE_UPDATE_WATCH")
            with (results / "RUN_DETAILS.json").open(encoding="utf-8") as f:
                details = json.load(f)
            self.assertEqual(details["source_stats"]["change_rows"],1)

if __name__ == "__main__":
    unittest.main()
