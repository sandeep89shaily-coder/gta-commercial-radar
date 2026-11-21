"""Regression for November 21: 158 Toronto changes, separately observed
Guelph application change, and unchanged Peel records are different states.
"""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from gta_unified_municipal_daily import run,OUTPUT,CITY
from gta_freshness_first_daily_selection import run as fresh

def write(path,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader();w.writerows(rows)
def read(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

class CrossMunicipalDaily(unittest.TestCase):
    def test_multicity_change_join_preserves_current_activity_not_old_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write(root/"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[{
                "observation":"FIRST_OBSERVED","city":"Toronto","address":"15 Sinclair St",
                "project_id":"toronto:26-001","source_record_date":"2026-11-20",
                "last_seen_local":"2026-11-21","first_seen_local":"2026-11-21",
                "description":"Warehouse conversion to new commercial commissary kitchen interior fit-out.",
                "current_source_status":"Under Review",
            }])
            write(root/"GTA_RADAR_GUELPH_GIS_NEW_OR_CHANGED.csv",[{
                "observation":"RECORD_CHANGED","city":"Guelph","project_id":"GUELPH:G-1",
                "application_id":"OZS26-018","address":"137 Poppy Drive West",
                "first_seen_local":"2026-11-03","source_record_date":"2026-10-15",
                "description":"A temporary sales office conversion for a multi unit development",
                "source_url":"https://guelph.ca/planning/OZS26-018",
            }])
            write(root/"GTA_RADAR_DAILY_PUBLIC_RECORDS.csv",[{
                "city":"Brampton","observation":"UNCHANGED",
                "project_id":"brampton:1","source_record_date":"2026-11-20",
            },{"city":"Mississauga","observation":"UNCHANGED",
                "project_id":"mississauga:1","source_record_date":"2026-11-20"}])
            result=run(root,today=dt.date(2026,11,21))
            self.assertEqual(result["primary_daily_new"],1)
            self.assertEqual(result["secondary_changed"],1)
            self.assertEqual(result["unified_change_rows"],2)
            self.assertEqual(read(root/OUTPUT)[1]["city"],"Guelph")
            self.assertEqual(read(root/OUTPUT)[1]["freshness_band"],
                             "OLDER_OR_UNKNOWN_APPLICATION_EVENT_REVIEW")
            city={x["city"]:x for x in read(root/CITY)}
            self.assertEqual(city["Brampton"]["public_feed_unchanged"],"1")
            self.assertEqual(city["Mississauga"]["public_feed_unchanged"],"1")
            self.assertEqual(city["Brampton"]["live_source_change_evidence"],"0")
            selected=fresh(root,today=dt.date(2026,11,21))
            self.assertTrue(selected["cross_city_reconciliation_used"])
            self.assertEqual(selected["general_top10_count"],1)

    def test_baseline_never_becomes_new_lead(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write(root/"GTA_RADAR_MUNICIPAL_PROJECT_CHANGES.csv",[{
                "observation":"INITIAL_BASELINE","city":"Burlington",
                "application_id":"ZBA-1","description":"New industrial warehouse expansion building"
            }])
            result=run(root,today="2026-11-21")
            self.assertEqual(result["secondary_new"],0)
            self.assertEqual(result["unified_change_rows"],0)

if __name__=="__main__":unittest.main()
