"""Regression for November 21: 158 Toronto changes, separately observed
Guelph application change, and unchanged Peel records are different states.
"""
import csv
import json
import os
import ssl
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from municipal_meeting_capture import OFFICIAL, fetch_html
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

    def test_additional_city_change_feeds_reach_five_day_export(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write(root/"GTA_RADAR_FIVE_CITY_OFFICIAL_NEW_OR_CHANGED.csv",[{
                "observation":"FIRST_OBSERVED","city":"Burlington",
                "project_id":"BURLINGTON:SP-26-77",
                "application_id":"SP-26-77",
                "address":"100 Commerce Road",
                "description":"New industrial warehouse construction and commercial expansion project",
                "first_seen_local":"2026-11-22",
                "source_record_date":"2026-11-20",
                "current_status":"Under Review",
                "source_url":"https://www.burlington.ca/en/building-and-renovating/current-development-projects.aspx"
            }])
            write(root/"GTA_RADAR_MARKHAM_CIRCULATION_CHANGES.csv",[{
                "observation":"INITIAL_BASELINE","city":"Markham",
                "application_id":"M-26-25","address":"100 Example Rd",
                "proposed_use":"New industrial warehouse construction",
                "first_seen_local":"2026-11-22",
                "circulation_date":"2026-11-21",
                "pdf_url":"https://markham.ca/notice.pdf"
            }])
            stats=run(root,today="2026-11-22")
            self.assertEqual(stats["secondary_new"],1)
            self.assertGreaterEqual(stats["secondary_feed_count"],12)
            record=read(root/OUTPUT)[0]
            self.assertEqual(record["city"],"Burlington")
            self.assertEqual(record["source_record_date"],"2026-11-20")
            self.assertEqual(record["source_keys"],"SP-26-77")
            self.assertIn("NOT_FIRST_PUBLICATION",record["date_basis"])
            report=fresh(root,today="2026-11-22")
            self.assertEqual(report["general_all_research_count"],1)
            self.assertEqual(report["verified_first_publications"],0)

    def test_regional_status_aliases_and_current_source_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            day="2026-11-23"
            base=dict(address="17 Industrial Road",scope="New industrial warehouse construction project",
                      first_seen_local=day,source_date="2026-11-21")
            portal="https://gis.barrie.ca/planning"
            north=root/"GTA_RADAR_NORTHERN_MAJOR_CITY_SOURCE_CHANGES.csv"
            write(north,[dict(base,city="Barrie",candidate_id="north-1",application_id="X1",
                              observation="SOURCE_CHANGED_REVIEW",original_record_url=portal,source_index_url=portal)])
            write(root/"GTA_RADAR_FOUR_CITY_LIVE_APPLICATIONS.csv",[
                dict(base,city="Ajax",application_id="A1",source_url="https://ajax.ca/project/A1",
                     source_observation="FIRST_OBSERVED_NOT_FIRST_PUBLICATION"),
                dict(base,city="Ajax",application_id="A2",source_url="https://ajax.ca/project/A2",
                     source_observation="SOURCE_UPDATED_NOT_FIRST_PUBLICATION",changed_fields="description"),
                dict(base,city="Pickering",application_id="P1",source_observation="UNCHANGED"),
                dict(base,city="Windsor",application_id="W1",source_observation="INITIAL_BASELINE"),
                dict(base,city="Newmarket",application_id="N1",source_observation="FIRST_OBSERVED_NOT_FIRST_PUBLICATION"),
            ])
            healthy="LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE"
            (root/"GTA_RADAR_FOUR_CITY_SOURCE_STATUS.json").write_text(json.dumps({"city_status":[
                {"city":city,"status":healthy} for city in ("Ajax","Pickering","Windsor")
            ]+[{"city":"Newmarket","status":"BLOCKED_OR_FAILED_NO_NEW_LIVE_RECORDS"}]}))
            result=run(root,today=day)
            self.assertEqual(result["unified_change_rows"],3)
            self.assertEqual(result["secondary_new"],1)
            self.assertEqual(result["secondary_changed"],2)
            barrie=next(row for row in read(root/OUTPUT) if row["city"]=="Barrie")
            self.assertEqual(barrie["record_source_url"],"")
            self.assertEqual(barrie["official_source_portal_url"],portal)
            audit={row["city"]:row for row in read(root/CITY)}
            self.assertEqual(audit["Pickering"]["daily_activity"],"UNCHANGED")
            self.assertEqual(audit["Windsor"]["daily_activity"],"BASELINE")
            self.assertEqual(audit["Newmarket"]["source_access_state"],"BLOCKED_OR_FAILED")
            self.assertEqual(fresh(root,today=day)["general_all_research_count"],2)
            os.utime(north,(1,1))
            self.assertEqual(run(root,today=day,not_before=2)["unified_change_rows"],2)

    def test_meeting_retry_uses_verified_ca_and_preserves_403(self):
        url=OFFICIAL["Oakville"]
        response=MagicMock()
        response.__enter__.return_value.status=200
        response.__enter__.return_value.read.return_value=b"council agenda"
        error=URLError(ssl.SSLCertVerificationError("missing issuer"))
        ca=ssl.create_default_context()
        with patch("municipal_meeting_capture.urlopen",side_effect=[error,response]) as fetch, \
             patch("gta_stc_oak_official_recovery.secure_ca_bundle",return_value=ca):
            self.assertEqual(fetch_html(url),"council agenda")
            self.assertIs(fetch.call_args.kwargs["context"],ca)
            self.assertEqual(ca.verify_mode,ssl.CERT_REQUIRED)
        with patch("municipal_meeting_capture.urlopen",
                   side_effect=HTTPError(url,403,"Forbidden",{},None)) as fetch:
            with self.assertRaises(HTTPError):
                fetch_html(url)
            fetch.assert_called_once()

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
