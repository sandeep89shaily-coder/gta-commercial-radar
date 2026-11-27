import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from gta_ero_notice_detail import parse_notice_html
from gta_fresh_customer_release_gate import _inventory
from gta_freshness_first_daily_selection import EQUIPMENT_ALL
from gta_industrial_equipment_pilot import equipment_changes
from gta_industrial_review_cursor import select
from gta_lifecycle_collected_sources import scan
from gta_mississauga_detail_recovery import ARCHIVED_DECISIONS, INDEX, run as mississauga
from gta_official_industrial_announcement_monitor import FRESH, run as monitor


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class November27RunRepairs(unittest.TestCase):
    def test_exception_notice_and_decision_use_their_own_sections(self):
        city = "<h3>Site address</h3><p>1 Test Road</p><p>Toronto, ON</p>"
        for header, details, stage in (
            ("<h2>Exception summary</h2><p>Exception posted November 26, 2026</p>",
             "Exception details", "Exception"),
            ("<p>Notice stage Decision</p><p>Decision posted November 26, 2026</p>",
             "Decision details", "Decision"),
        ):
            page = ("<h1>Test Industrial</h1><p>026-0001</p>" + header + city
                    + f"<h2>{details}</h2><p>A new fuel-powered generator powers the building.</p>")
            notice = parse_notice_html(page, "026-0001", "https://ero.ontario.ca/notice/026-0001")
            self.assertEqual(notice["notice_stage"], stage)
            self.assertEqual(notice[stage.lower() + "_posted"], "2026-11-26")
            self.assertEqual(equipment_changes(notice["proposal_details"])[0]["equipment"],
                             "Power generator")

    def test_old_notice_number_with_current_dated_change_selected_first(self):
        cards = {"026-0001": {"last_updated": "2026-11-27"},
                 "026-1200": {"last_updated": "2026-10-27"}}
        self.assertEqual(list(select(cards, {}, 1)), ["026-0001"])

    def test_federal_updated_date_does_not_supply_publication(self):
        atom = (b"<feed><entry><title>Test manufacturer expands production</title>"
                b"<updated>2026-11-27</updated><link href='https://www.canada.ca/en/"
                b"economic-development-southern-ontario/news/2026/test.html'/></entry></feed>")
        with tempfile.TemporaryDirectory() as folder:
            result = monitor(folder, today="2026-11-27", fetcher=lambda url: atom,
                             feeds={"FEDDEV_ONTARIO": "test"})
            self.assertEqual(result["source_health"]["FEDDEV_ONTARIO"]["article_links"], 1)
            self.assertEqual(result["recent_publisher_dated_research"], 0)

    def test_watchlist_uses_current_dated_feeds_and_marks_name_match_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_csv(root / FRESH, [
                {"publisher_reported_date": "2026-11-27",
                 "source_url": "https://news.ontario.ca/example", "title": "Fowler Metal Industries expands"},
                {"publisher_reported_date": "2026-11-22",
                 "source_url": "https://news.ontario.ca/stale", "title": "Fowler Metal Industries invests"},
            ])
            timestamp = (root / FRESH).stat().st_mtime
            projects = [{"project_id": "LC-055", "name": "Fowler Metal Industries"}]
            files, candidates = scan(root, projects, dt.date(2026, 11, 27), timestamp)
            self.assertEqual(files[FRESH], 1)
            self.assertEqual(len(candidates["LC-055"]), 1)
            self.assertFalse(scan(root, projects, dt.date(2026, 11, 27), timestamp + 1)[0])

    def test_release_handoff_uses_inclusive_five_calendar_days(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_csv(root / EQUIPMENT_ALL, [
                {"project_or_company": f"Test project {day}", "city": "Toronto",
                 "source_event_date": f"2026-11-{day}",
                 "source_url": f"https://news.ontario.ca/{day}", "scope": "Industrial equipment"}
                for day in (22, 23, 27, 28)
            ])
            records = _inventory(root, five_day_as_of=dt.date(2026, 11, 27))
            self.assertEqual({row["source_event_date"] for row in records.values()},
                             {"2026-11-23", "2026-11-27"})

    def test_mississauga_refusal_is_recovered_as_historical_disposition(self):
        old_url = ("https://www.mississauga.ca/services-and-programs/planning-and-development/"
                   "development-applications/active-development-applications/1075-canadian-place-t-oz-26-2-w3/")

        def fetch(url):
            if url == old_url:
                raise ValueError("HTTP_404_OR_REDIRECT")
            self.assertEqual(url, ARCHIVED_DECISIONS["TOZ262W3"])
            return "<main><h1>T-OZ 26-2 W3 – Notice of Refusal</h1><p>1075 Canadian Place</p></main>"

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_csv(root / INDEX, [{
                "project_id": "EARLY_APP:MISSISSAUGA:OZ26-2W3", "city": "Mississauga",
                "application_id": "T-OZ 26-2 W3", "record_source_url": old_url,
            }])
            report = mississauga(root, today=dt.date(2026, 11, 27), fetcher=fetch)
            self.assertEqual(report["archived_refusal_notices_verified"], 1)
            self.assertEqual(report["pages_collected"], 0)
            self.assertEqual(report["page_failures"], [])
