"""Toronto City Clerk official schedule is not a published TMMIS agenda."""
import datetime as dt
import json
import socket
import tempfile
import unittest
from pathlib import Path

from gta_toronto_official_schedule import (
    parse, run, _official_csv_url, fetch_csv, RESOURCE_ID, METADATA_URL,
    RESULTS_CSV, STATUS
)

SAMPLE = ("_id,Term,Committee,MTG #,Date,Start Time,End Time,Location\n"
          "1,2022-2026,Planning and Housing Committee,30,2026-11-16,09:30 AM,18:00 PM,City Hall\n"
          "2,2022-2026,Economic and Community Development Committee,19,2026-11-20,09:30 AM,18:00 PM,City Hall\n"
          "3,2022-2026,Audit Committee,4,2026-11-17,09:30 AM,18:00 PM,City Hall\n"
          "4,2022-2026,Planning and Housing Committee,25,2026-08-16,09:30 AM,18:00 PM,City Hall\n")

AT = dt.datetime(2026, 11, 13, tzinfo=dt.timezone.utc)

class FakeResponse:
    def __init__(self, url, data, mime):
        self.url = url
        self.status_code = 200
        self.headers = {"Content-Type": mime}
        self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def iter_content(self, chunk_size=65536): yield self.data

class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}
        self.trust_env = True
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses[url]

def resolver(host, port, *, type):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

class TorontoOfficialScheduleTests(unittest.TestCase):
    def test_recent_schedule_rows_no_fake_agendas(self):
        rows, total = parse(SAMPLE, now=AT)
        self.assertEqual(total, 4)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["committee"], "Planning and Housing Committee")
        self.assertEqual(rows[0]["meeting_number"], "30")
        self.assertTrue(all(not row["agenda_url"] for row in rows))
        self.assertTrue(all(not row["project_verified"] for row in rows))

    def test_held_unknown_schema_and_non_official_resource(self):
        with self.assertRaises(ValueError):
            parse("Date,Meeting\n2026-11-16,PH30\n", now=AT)
        with self.assertRaises(ValueError):
            _official_csv_url("https://evil.example/a.csv")
        with self.assertRaises(ValueError):
            _official_csv_url("https://ckan0.cf.opendata.inter.prod-toronto.ca/x.pdf")

    def test_only_two_pinned_policy_checked_gets(self):
        url = "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/source.csv"
        metadata = json.dumps({"success": True, "result": {
            "id": RESOURCE_ID, "format": "CSV", "url": url
        }}).encode()
        fake = FakeSession({
            METADATA_URL: FakeResponse(METADATA_URL, metadata, "application/json"),
            url: FakeResponse(url, SAMPLE.encode(), "text/csv")
        })
        data, origin = fetch_csv(session=fake, resolver=resolver,
                                policy_reader=lambda _: (200, "User-agent: *\nAllow: /"))
        self.assertEqual(data, SAMPLE)
        self.assertEqual(origin, url)
        self.assertEqual(len(fake.calls), 2)
        self.assertTrue(all(not call[1]["allow_redirects"] for call in fake.calls))

    def test_results_stay_review_only_and_refuse_lost_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run(root, csv_text=SAMPLE, now=AT)
            self.assertEqual(result["recent_scheduled_meetings"], 3)
            self.assertEqual(result["agenda_urls_discovered"], 0)
            self.assertEqual(result["verified_projects"], 0)
            self.assertEqual(result["paid_ai_calls"], 0)
            self.assertTrue((root/RESULTS_CSV).is_file())
            history = (root/RESULTS_CSV).read_bytes()
            bad = run(root, csv_text="invalid,schema\nx,thing\n", now=AT)
            self.assertEqual(bad["status"], "OFFICIAL_SCHEDULE_BLOCKED_OR_SCHEMA_HELD")
            self.assertEqual((root/RESULTS_CSV).read_bytes(), history)
            self.assertTrue((root/STATUS).is_file())

    def test_default_does_not_fetch_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(tmp)
            self.assertEqual(result["status"], "NO_FETCH_HISTORICAL_REVIEW")
            self.assertFalse((Path(tmp)/RESULTS_CSV).exists())

if __name__ == "__main__":
    unittest.main()
