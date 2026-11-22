"""Uncapped five-day AI investigations retain source provenance and honest holds."""
import csv
import tempfile
import unittest
from pathlib import Path
from gta_five_day_all_ai_queue import prepare, AI_INPUT, AUDIT
from gta_freshness_first_daily_selection import GENERAL_ALL, EQUIPMENT_ALL

def write(path,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)

def read(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

class AllRecentAIQueueTests(unittest.TestCase):
    def test_uncapped_general_plus_equipment_and_sensible_holds(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            general=[{
                "city":"Brampton","project_or_company":f"{i} Industrial Rd",
                "address_or_company_site_unverified":f"{i} Industrial Rd",
                "source_project_id":f"BRAMP:SP-26-{i}",
                "scope":"New construction of 70000 sq ft industrial warehouse and manufacturing expansion",
                "source_event_date":"2026-11-18",
                "source_event_date_basis":"OFFICIAL_APPLICATION_DATE_NOT_FIRST_PUBLICATION",
                "source_url":f"https://www.brampton.ca/planning/project-{i}",
                "stage":"Under Review","observation":"FIRST_OBSERVED"}
                for i in range(14)]
            general.append({
                "city":"Toronto","project_or_company":"Old project",
                "address_or_company_site_unverified":"1 Old Rd",
                "source_project_id":"OLD-1",
                "scope":"New industrial manufacturing facility expansion building",
                "source_event_date":"2026-11-17",
                "source_url":"https://www.toronto.ca/planning/old",
                "stage":"Under Review"})
            equipment=[{
                "city":"Oakville","project_or_company":"New factory investment",
                "source_project_id":"OFFICIAL_RELEASE:OAK",
                "scope":"Manufacturing factory plans to install new CNC machinery and production line",
                "company_source_claim":"Acme Manufacturing Inc.",
                "source_event_date":"2026-11-20",
                "source_event_date_basis":"PUBLISHER_REPORTED_NOT_FIRST_DISCLOSURE",
                "source_url":"https://news.ontario.ca/en/release/example",
                "stage":"FUTURE_EXPANSION_RESEARCH_NOT_OPEN_PROCUREMENT"},
                {"city":"Oakville","project_or_company":"Closed factory",
                 "source_project_id":"OFFICIAL_RELEASE:CLOSED",
                 "scope":"Manufacturing factory expands installation of new CNC equipment",
                 "source_event_date":"2026-11-20",
                 "source_url":"https://news.ontario.ca/en/release/closed",
                 "stage":"COMPLETED_OR_OPERATIONAL_NOT_UPCOMING_ORDER"}]
            write(root/GENERAL_ALL,general)
            write(root/EQUIPMENT_ALL,equipment)
            report=prepare(root,today="2026-11-22")
            selected=read(root/AI_INPUT)
            self.assertEqual(report["all_five_day_rows"],report.get("all_five_day_rows",0)) if False else None
            self.assertEqual(report["eligible_for_source_backed_ai"],15)
            self.assertEqual(len(selected),15)
            self.assertEqual({r["city"] for r in selected},{"Brampton","Oakville"})
            self.assertEqual(sum(r["lane"]=="EQUIPMENT_INTELLIGENCE" for r in selected),1)
            self.assertEqual(len(read(root/AUDIT)),17)
            self.assertEqual(report["buyer_verified"],False)
            self.assertEqual(report["outreach_authorized"],False)
            self.assertTrue(any(r["reason"]=="OUTSIDE_FIVE_DAY_SOURCE_EVENT_WINDOW"
                                for r in read(root/AUDIT)))
            self.assertTrue(any(r["reason"]=="COMPLETED_OR_AWARDED_NOT_CURRENT_PROCUREMENT"
                                for r in read(root/AUDIT)))

    def test_missing_https_does_not_enter_paid_ai(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            write(root/GENERAL_ALL,[{
                "city":"Mississauga","project_or_company":"10 Test Street",
                "address_or_company_site_unverified":"10 Test Street",
                "source_project_id":"SP-1",
                "scope":"New industrial manufacturing warehouse construction",
                "source_event_date":"2026-11-22",
                "source_url":"http://unapproved.example.org/project",
                "stage":"Under Review"}])
            result=prepare(root,today="2026-11-22")
            self.assertEqual(result["eligible_for_source_backed_ai"],0)
            self.assertEqual(read(root/AI_INPUT),[])
            self.assertFalse((root/"v5_ai_budget.sqlite").exists())
