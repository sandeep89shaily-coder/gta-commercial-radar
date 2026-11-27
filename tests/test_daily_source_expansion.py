import csv
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path

import gta_public_procurement as bids
import gta_utility_milestones as utility
from gta_fresh_customer_release_gate import _inventory
from gta_official_industrial_announcement_monitor import run as announcements

DAY = dt.date(2026, 11, 27)
ANNUAL = "2026-2027-awardNotice-avisAttribution.csv"
OPEN_FIELDS = ["referenceNumber-numeroReference", "title-titre-eng", "solicitationNumber-numeroSollicitation",
               "publicationDate-datePublication", "regionsOfDelivery-regionsLivraison-eng",
               "tenderStatus-appelOffresStatut-eng", "tenderClosingDate-appelOffresDateCloture",
               "amendmentDate-dateModification", "contractingEntityName-nomEntitContractante-eng"]
AWARD_FIELDS = OPEN_FIELDS[:5] + [OPEN_FIELDS[-1], "awardStatus-attributionStatut-eng",
               "contractAwardDate-dateAttributionContrat", "supplierLegalName-nomLegalFournisseur-eng"]


def csv_bytes(fields, rows=()):
    handle = io.StringIO()
    writer = csv.writer(handle)
    writer.writerow(fields)
    writer.writerows(rows)
    return handle.getvalue().encode()


def report_rows(root, filename):
    with (root / filename).open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


class ProcurementSources(unittest.TestCase):
    def test_distinguishes_new_older_same_day_and_already_awarded(self):
        def record(ref, issue, close, region="Ontario"):
            return [ref, "Generator parts", ref, issue, region, "Open", close, "", "Public Buyer"]

        def download(url, limit=None):
            if url.startswith(bids.API):
                raise OSError("temporarily unavailable")
            if url.endswith(bids.CANADA_OPEN):
                return csv_bytes(OPEN_FIELDS, [
                    record("fresh", "2026-11-23", "2026-12-03"),
                    record("old", "2026-11-22", "2026-12-03"),
                    record("closes-today", "2026-11-27", "2026-11-27"),
                    record("awarded", "2026-11-25", "2026-12-03"),
                    record("outside", "2026-11-27", "2026-12-03", "British Columbia"),
                ])
            if url.endswith(bids.CANADA_NEW):
                row = record("new-only", "2026-11-27", "2026-12-07")
                row[-2] = DAY.isoformat()
                return csv_bytes(OPEN_FIELDS + ["amendmentNumber-numeroModification"], [row + ["000"]])
            self.assertTrue(url.endswith(ANNUAL))
            return csv_bytes(AWARD_FIELDS, [
                ["award-ref", "Generator parts", "awarded", "2026-11-26", "Ontario",
                 "Public Buyer", "Active", "2026-11-26", "Example Inc."],
            ])

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            summary = bids.run(root, today=DAY, download=download)
            rolling = {r["record_id"]: r for r in report_rows(root, bids.FIVE_DAY)}
            self.assertEqual(set(rolling), {"fresh", "new-only"})
            self.assertEqual(rolling["new-only"]["procurement_state"],
                             "NEW_NOTICE_PENDING_OPEN_SNAPSHOT_RECHECK")
            self.assertEqual(summary["recent_awards"], 1)
            self.assertEqual(len(_inventory(root, five_day_as_of=DAY, include_shortlist=False)), 2)
            self.assertFalse(_inventory(root, five_day_as_of=DAY + dt.timedelta(days=1)))

    def test_only_observed_material_change_uses_amendment_date(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            close, amendment = "2026-12-02", ""

            def download(url, limit=None):
                if url.startswith(bids.API):
                    raise OSError("temporarily unavailable")
                if url.endswith(bids.CANADA_OPEN):
                    return csv_bytes(OPEN_FIELDS, [
                        ["x", "Industrial pump", "x", "2026-11-08", "Ontario",
                         "Open", close, amendment, "Public Buyer"],
                    ])
                return csv_bytes(AWARD_FIELDS if url.endswith(ANNUAL) else OPEN_FIELDS)

            bids.run(root, today=DAY - dt.timedelta(days=1), download=download)
            close, amendment = "2026-12-09", DAY.isoformat()
            bids.run(root, today=DAY, download=download)
            row, = report_rows(root, bids.FIVE_DAY)
            self.assertEqual(row["publication_date"], "2026-11-08")
            self.assertEqual(row["source_event_type"], "PUBLISHER_DATED_MATERIAL_AMENDMENT")

    def test_toronto_uses_official_award_format(self):
        identity = "e211f003-5909-4bea-bd96-d75899d8e612"

        def download(url, limit=None):
            if url.startswith(bids.API):
                return json.dumps({"success": True, "result": {"name": bids.TORONTO_AWARDS,
                    "license_title": "open-government-licence-toronto", "resources": [
                        {"id": identity, "datastore_active": True, "metadata_modified": DAY.isoformat()}
                    ]}}).encode()
            award = json.dumps([{"AwardedDate": DAY.isoformat(), "Successful_Bidder": "Example Inc."}])
            return csv_bytes(["Document Number", "Solicitation Document Description", "Division", "Award"],
                             [["1234567890", "Industrial pump repair", "Toronto Water", json.dumps(award)]])

        rows, date = bids._toronto(bids.TORONTO_AWARDS, download, DAY)
        self.assertEqual(rows[0]["supplier"], "Example Inc.")
        self.assertEqual(rows[0]["award_date"], DAY.isoformat())


class ProjectSources(unittest.TestCase):
    def test_oeb_source_date_and_ieso_undated_changes(self):
        table = b"""<table><tr><th>Case No.</th><th>Date Filed</th><th>Case Description</th>
          <th>Category</th><th>Applicant</th></tr><tr><td>EB-2026-0001</td>
          <td>Nov 27, 2026</td><td>Transmission station</td><td>Facilities</td>
          <td>Utility Inc.</td></tr></table>"""
        facility = {"CaaIdAndDate": "2026-111", "Name": "New station", "Type": "Increase Load",
                    "Applicant": "Factory Inc.", "SiaStatus": "Active"}

        def fetch(url):
            if url == utility.OEB_APPLICATIONS:
                return table
            if url == utility.IESO_QUEUE:
                return json.dumps([facility]).encode()
            raise OSError("nothing fetched")

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = utility.run(root, today=DAY, fetch=fetch)
            self.assertEqual(result["five_day_dated_utility_milestones"], 1)
            facility["SiaStatus"] = "Final"
            result = utility.run(root, today=DAY, fetch=fetch)
            self.assertEqual(result["ieso_changed_rows"], 1)
            self.assertEqual(result["five_day_dated_utility_milestones"], 1)
            ieso = next(r for r in report_rows(root, utility.OUTPUT) if r["source"] == "IESO_QUEUE")
            self.assertEqual(ieso["source_event_date"], "")
            self.assertEqual(ieso["procurement_status"], "UNKNOWN")

    def test_ontario_manufacturing_program_is_searchable_in_announcement_feed(self):
        data = b"""<rss><channel><item><title>Ontario invests in Example Works</title>
          <description>Funding through AMIC will support the project.</description>
          <pubDate>Fri, 27 Nov 2026 12:00:00 GMT</pubDate>
          <link>https://news.ontario.ca/en/release/123/example</link></item></channel></rss>"""
        with tempfile.TemporaryDirectory() as folder:
            report = announcements(folder, today=DAY, feeds={"ONTARIO_NEWSROOM": "test"},
                                   fetcher=lambda url: data)
            self.assertEqual(report["recent_ontario_manufacturing_funding_signals"], 1)
