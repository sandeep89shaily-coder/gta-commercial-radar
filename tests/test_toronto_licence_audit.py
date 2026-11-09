"""Small read-only regression for aggregate Toronto licence diagnostics."""
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gta_toronto_licence_audit import analyze

class TorontoLicenceAuditTests(unittest.TestCase):
    def test_aggregate_audit_never_emits_business_identity(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"radar.sqlite"
            with sqlite3.connect(db) as con:
                con.executescript("""
                    CREATE TABLE records_current(
                        source_id TEXT, record_key TEXT, first_seen_at TEXT,
                        source_date TEXT, active INTEGER);
                    CREATE TABLE record_versions(
                        version_id INTEGER PRIMARY KEY, source_id TEXT,
                        record_key TEXT, payload_json TEXT);
                """)
                rows=[
                    ("one", {"Category":"EATING OR DRINKING ESTABLISHMENT",
                             "Licence Address Line 1":"100 Queen Street West",
                             "Operating Name":"PRIVATE-BUSINESS-DO-NOT-EXPORT",
                             "Issued":"2026-11-08","Cancel Date":""}),
                    ("two", {"Category":"EATING OR DRINKING ESTABLISHMENT",
                             "Licence Address Line 1":"",
                             "Operating Name":"PRIVATE-SECOND-DO-NOT-EXPORT",
                             "Issued":"2026-11-08","Cancel Date":""}),
                    ("three", {"Category":"EATING OR DRINKING ESTABLISHMENT",
                               "Licence Address Line 1":"100 Queen Street West",
                               "Issued":"2021-08-01","Cancel Date":""})
                ]
                for i,(key,payload) in enumerate(rows,1):
                    con.execute("INSERT INTO records_current VALUES (?,?,?,?,1)",
                                ("toronto_business_licences",key,"2026-11-09",
                                 "2026-11-09"))
                    con.execute("INSERT INTO record_versions VALUES (?,?,?,?)",
                                (i,"toronto_business_licences",key,json.dumps(payload)))
            out=analyze(db,as_of=dt.date(2026,11,9),limit=100)
            self.assertEqual(out["active_records_in_ledger"],3)
            self.assertEqual(out["metric_counts"]["recent_active_target_even_without_site"],2)
            self.assertEqual(out["metric_counts"]["recent_active_target_with_site"],1)
            self.assertEqual(out["sequential_classification_counts"]["ACCEPTED"],1)
            encoded=json.dumps(out)
            self.assertNotIn("PRIVATE-BUSINESS",encoded)
            self.assertNotIn("100 Queen Street",encoded)
            self.assertNotIn('"one"',encoded)
            self.assertIn("Licence Address Line 1",encoded)

if __name__=="__main__":
    unittest.main()
