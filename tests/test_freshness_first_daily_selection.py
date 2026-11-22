"""Freshness-first selection must never pad a Top 10 with older grants."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from gta_freshness_first_daily_selection import (
    run, GENERAL_TOP, EQUIPMENT_TOP, GENERAL_ALL, EQUIPMENT_ALL, WATCHLIST, STATUS,
)

def write(path,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)

def read(path):
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

class DailyFreshnessFirstTests(unittest.TestCase):
    def test_new_recent_permit_promoted_older_and_nonmaterial_change_held(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write(root/"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[
                {"observation":"FIRST_OBSERVED","first_seen_local":"2026-11-20",
                 "last_seen_local":"2026-11-20","project_id":"toronto:sinclair",
                 "city":"Toronto","address":"15 Sinclair Street",
                 "description":"Vacant industrial warehouse conversion to new commercial commissary kitchen fit-out.",
                 "source_record_date":"2026-11-18",
                 "stage_from_local_status":"PRE_APPROVAL",
                 "current_source_status":"Under Review"},
                {"observation":"FIRST_OBSERVED","first_seen_local":"2026-11-20",
                 "last_seen_local":"2026-11-20","project_id":"barrie:old",
                 "city":"Barrie","address":"100 Example Road",
                 "description":"New industrial warehouse construction and office renovation.",
                 "source_record_date":"2025-03-18",
                 "stage_from_local_status":"PRE_APPROVAL",
                 "current_source_status":"Under Review"},
                {"observation":"RECORD_CHANGED","first_seen_local":"2026-10-30",
                 "last_seen_local":"2026-11-20","project_id":"toronto:vet",
                 "city":"Toronto","address":"1200 Dundas Street",
                 "description":"Vacant commercial unit interior alteration for a veterinary clinic.",
                 "source_record_date":"2026-11-17",
                 "changed_fields":"source_keys | current_source_status",
                 "stage_from_local_status":"PRE_APPROVAL",
                 "current_source_status":"Under Review"},
            ])
            report=run(root,today=dt.date(2026,11,20))
            self.assertEqual(report["general_top10_count"],1)
            self.assertEqual(read(root/GENERAL_TOP)[0]["project_or_company"],"15 Sinclair Street")
            self.assertFalse(any(x["project_or_company"]=="100 Example Road" for x in read(root/GENERAL_TOP)))
            self.assertEqual(report["verified_first_publications"],0)
            self.assertEqual(len(read(root/WATCHLIST)),2)

    def test_recent_equipment_ero_only_and_old_funding_watchlisted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write(root/"GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv",[
                {"source_type":"ERO_INSTRUMENT_PROPOSAL","company":"New Equipment Inc",
                 "municipality":"Guelph","equipment_or_scope":"Installation of industrial scrubber equipment",
                 "source_date":"2026-11-19","source_url":"https://ero.ontario.ca/notice/example",
                 "source_date_basis":"ERO_NOTICE_POSTING_NOT_FIRST_EQUIPMENT_ORDER"},
                {"source_type":"ERO_INSTRUMENT_PROPOSAL","company":"Old Equipment Inc",
                 "municipality":"Oakville","equipment_or_scope":"Replacement of warehouse dust collector",
                 "source_date":"2026-11-06","source_url":"https://ero.ontario.ca/notice/old"}
            ])
            write(root/"GTA_RADAR_FEDERAL_CAPEX_TOP20_RESEARCH.csv",[
                {"research_rank":"1","recipient":"CMI Heavy Industries",
                 "funding_record_id":"GRANT-2025","evidence_scope":"CNC boring mill",
                 "agreement_date_not_publication":"2025-12-15"}
            ])
            result=run(root,today=dt.date(2026,11,20))
            self.assertEqual(result["equipment_top10_count"],1)
            self.assertEqual(read(root/EQUIPMENT_TOP)[0]["project_or_company"],"New Equipment Inc")
            self.assertEqual(len(read(root/WATCHLIST)),2)
            self.assertEqual(result["verified_buyers"],0)

    def test_no_new_sources_never_recycles_old_top10(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            result=run(root,today="2026-11-20")
            self.assertEqual(result["general_top10_count"],0)
            self.assertEqual(result["equipment_top10_count"],0)
            self.assertEqual(len(read(root/GENERAL_TOP)),0)
            self.assertTrue((root/STATUS).is_file())


    def test_five_calendar_day_window_uncapped_and_weekend_carryover(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            day=dt.date(2026,11,22)
            # More than ten genuinely source-recent, independently identified
            # application records must survive, while legacy Top 10 remains.
            write(root/"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv", [
                {"observation":"FIRST_OBSERVED",
                 "first_seen_local":"2026-11-22",
                 "last_seen_local":"2026-11-22",
                 "project_id":f"toronto:project-{i}",
                 "city":"Toronto","address":f"{i} Test Road",
                 "description":"New industrial warehouse construction and commercial tenant fit-out.",
                 "source_record_date":"2026-11-18",
                 "current_source_status":"Under Review"}
                for i in range(12)
            ] + [
                {"observation":"FIRST_OBSERVED",
                 "first_seen_local":"2026-11-22",
                 "last_seen_local":"2026-11-22",
                 "project_id":"toronto:expired","city":"Toronto",
                 "address":"999 Expired Road",
                 "description":"New industrial warehouse construction and commercial tenant fit-out.",
                 "source_record_date":"2026-11-17",
                 "current_source_status":"Under Review"}
            ])
            # This was discovered before Sunday but was unchanged during the
            # Sunday collection. It is retained as research, NOT a new event.
            write(root/"GTA_RADAR_DAILY_PUBLIC_RECORDS.csv", [
                {"observation":"UNCHANGED","first_seen_local":"2026-11-19",
                 "last_seen_local":"2026-11-22",
                 "project_id":"brampton:industrial-renovation",
                 "city":"Brampton","address":"99 Summerlea Road",
                 "description":"Alteration (Renovation) F2: Industrial",
                 "source_record_date":"2026-11-18",
                 "current_source_status":"Applied"},
                {"observation":"UNCHANGED","first_seen_local":"2026-11-12",
                 "last_seen_local":"2026-11-22",
                 "project_id":"brampton:stale",
                 "city":"Brampton","address":"100 Historical Road",
                 "description":"New industrial warehouse construction and office addition.",
                 "source_record_date":"2026-11-18",
                 "current_source_status":"Applied"},
            ])
            report=run(root,today=day)
            self.assertEqual(report["selection_window_days_inclusive"],5)
            self.assertEqual(report["general_all_research_count"],13)
            self.assertEqual(report["general_top10_count"],10)
            self.assertEqual(len(read(root/GENERAL_ALL)),13)
            self.assertEqual(len(read(root/GENERAL_TOP)),10)
            carried=[r for r in read(root/GENERAL_ALL) if r["city"]=="Brampton"]
            self.assertEqual(len(carried),1)
            self.assertEqual(carried[0]["freshness_class"],
                "RECENT_UNCHANGED_RESEARCH_NOT_NEW_DISCLOSURE")
            self.assertEqual(carried[0]["decision"],
                "RESEARCH_ONLY_PREVIOUSLY_OBSERVED")
            self.assertFalse(any(r["project_or_company"]=="999 Expired Road"
                for r in read(root/GENERAL_ALL)))
            self.assertEqual(report["verified_buyers"],0)

    def test_equipment_uncapped_five_day_export(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write(root/"GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv", [
                {"source_type":f"ERO_PROPOSAL_{i}",
                 "company":f"Manufacturer {i}",
                 "municipality":"Oakville",
                 "equipment_or_scope":"Installation of industrial scrubber equipment",
                 "source_date":"2026-11-18",
                 "source_date_basis":"SOURCE_RECORD_NOT_OPEN_ORDER",
                 "source_url":f"https://ero.ontario.ca/notice/example-{i}"}
                for i in range(12)
            ])
            report=run(root,today="2026-11-22")
            self.assertEqual(report["equipment_all_research_count"],12)
            self.assertEqual(len(read(root/EQUIPMENT_ALL)),12)
            self.assertEqual(len(read(root/EQUIPMENT_TOP)),10)
            self.assertEqual(report["verified_open_supplier_contracts"],0)

if __name__=="__main__": unittest.main()
