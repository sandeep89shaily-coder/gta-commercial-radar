"""No-network dashboard tests for actual V8 and early source data."""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import radar_workspace as rw
import radar_operations_dashboard as dash


class DashboardTests(unittest.TestCase):
    def test_shows_v8_and_early_source_history(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);rw.setup(home)
            dbfile=home/"Data"/rw.DB_NAME
            with closing(sqlite3.connect(dbfile)) as db:
                db.execute("INSERT INTO source_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                    "original",1,"brampton_building_permits","2026-10-25",
                    "2026-10-25",0,0,500,0,0,0,"2026-10-25","HTTP 502","{}"))
                db.execute("INSERT INTO import_runs(import_id,started_at,completed_at,roots_json) "
                           "VALUES(?,?,?,?)",("x","2026-10-25","2026-10-25","[]"))
                db.execute("INSERT INTO feed_health VALUES(?,?,?,?,?)",(
                    "x","feddev_investment","early_sources.csv","SUCCESS",
                    json.dumps({"fetched":"31"})))
                db.execute("INSERT INTO historical_events VALUES(?,?,?,?,?,?,?)",(
                    "k","brampton_building_permits","1","UPDATED",
                    "2026-10-25T10:00:00","p",
                    json.dumps({"title":"<script>alert(1)</script>",
                                "source_url":"javascript:alert(2)"})))
                db.commit()
            rendered=dash.build(home).read_text(encoding="utf-8")
            self.assertIn("brampton_building_permits",rendered)
            self.assertIn("feddev_investment",rendered)
            self.assertIn("HTTP 502",rendered)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;",rendered)
            self.assertNotIn("href='javascript:",rendered)
            self.assertIn("DeepSeek OFF",rendered)
            self.assertIn("refresh",rendered)


if __name__=="__main__":
    unittest.main()
