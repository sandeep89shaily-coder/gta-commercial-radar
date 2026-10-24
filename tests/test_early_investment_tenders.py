"""Offline tests of two distinct public investment / open procurement lanes."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
import early_investment_tenders as app

RSS=b"""<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>
<title>Ontario Newsroom</title>
<item><title>Ontario supports new manufacturing plant in Brampton</title>
<link>https://news.ontario.ca/en/release/1000001/test</link>
<guid>ontario-release-1</guid>
<description>Company announces new plant expansion in Brampton.</description>
<pubDate>Fri, 23 Oct 2026 08:00:00 EST</pubDate></item>
<item><title>Ontario improves student programs</title>
<link>https://news.ontario.ca/en/release/1000002/test</link>
<guid>ontario-release-2</guid>
<description>Schools and training.</description>
<pubDate>Fri, 23 Oct 2026 08:00:00 EST</pubDate></item>
</channel></rss>"""

TENDER=("referenceNumber-numeroReference,title-titre-eng,publicationDate-datePublication,"
"tenderStatus-appelOffresStatut-eng,description-description-eng,"
"organizationName-nomOrganisation-eng,deliveryRegion-regionLivraison-eng,"
"tenderClosingDate-appelOffresdateCloture\n"
"2026-00001,Industrial refrigeration for Toronto plant,2026-10-23,Open,"
"Provide chiller equipment,Public Services Canada,Toronto Ontario,2026-11-04\n"
"2026-00002,Warehouse security access controls,2026-10-22,Open,"
"New building security,Public Services Canada,Edmonton Alberta,2026-11-03\n"
"2026-00003,Air conditioning maintenance,2026-10-11,Closed,"
"HVAC maintenance,Public Services Canada,Toronto Ontario,2026-10-22\n").encode("utf-8")


class R:
    def __init__(self,raw):self.content=raw
    def raise_for_status(self):pass

class S:
    def __init__(self,data):self.data=data
    def get(self,url,**kwargs):
        if url not in self.data:
            raise app.requests.RequestException("missing fixture")
        return R(self.data[url])


class Tests(unittest.TestCase):
    def test_ontario_investment_is_not_open_procurement(self):
        records=app.parse_ontario_rss(RSS)
        self.assertEqual(len(records),2)
        self.assertEqual(records[0]["commercial_fit"],"REVIEW")
        self.assertEqual(records[0]["source_date"],"2026-10-23")
        self.assertEqual(records[0]["geographic_confidence"],"GTA_TEXT_MENTION_UNVERIFIED_SITE")
        self.assertEqual(records[0]["procurement_status"],"UNKNOWN")
        self.assertEqual(records[1]["commercial_fit"],"LOW")

    def test_bad_rss_fails_no_fake_zero(self):
        for content in (b"not xml",b"<html><p>Access blocked</p></html>"):
            with self.assertRaises(RuntimeError):
                app.parse_ontario_rss(content)

    def test_open_tender_stays_federal_not_private(self):
        rows=app.parse_canadabuys_csv(TENDER)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["geographic_confidence"],"GTA_LOCATION_TEXT_REVIEW")
        self.assertEqual(rows[1]["geographic_confidence"],
                         "CANADA_WIDE_DELIVERY_NOT_CONFIRMED_GTA")
        self.assertEqual(rows[0]["procurement_status"],"OPEN_AT_SOURCE_SNAPSHOT_VERIFY_DEADLINE")
        self.assertEqual(rows[0]["source_date"],"2026-10-23")
        self.assertIn("FEDERAL_ORGANIZATION",rows[0]["company_role"])

    def test_schema_change_fails(self):
        with self.assertRaises(RuntimeError):
            app.parse_canadabuys_csv(b"title,other\nHello,world\n")

    def test_new_after_baseline_and_failed_source_preserves_history(self):
        with tempfile.TemporaryDirectory() as root:
            opts=dict(data_dir=Path(root)/"data",out_dir=Path(root)/"out",
                     sources=["ontario_investment_news"])
            data={app.RSS_URL:RSS}
            self.assertEqual(app.run(**opts,session=S(data),now="2026-10-24T11:00:00"),0)
            self.assertEqual(app.run(**opts,session=S(data),now="2026-10-25T11:00:00"),0)
            expanded=RSS.replace(b"</channel>",b"""<item>
<title>New warehouse in Mississauga</title>
<link>https://news.ontario.ca/en/release/1000003/test</link>
<guid>ontario-release-3</guid>
<description>New distribution centre in Mississauga</description>
<pubDate>Fri, 23 Oct 2026 09:00:00 EST</pubDate></item></channel>""")
            self.assertEqual(app.run(**opts,session=S({app.RSS_URL:expanded}),
                                     now="2026-10-26T11:00:00"),0)
            with (Path(root)/"out"/"EARLY_INVESTMENT_TENDERS_CHANGES.csv").open(
                         encoding="utf-8-sig",newline="") as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["change_type"],"NEW")
            self.assertEqual(app.run(**opts,session=S({}),now="2026-10-27T11:00:00"),1)
            db=sqlite3.connect(Path(root)/"data"/"early_investment_procurement_review.sqlite")
            self.assertEqual(db.execute("SELECT count(*) FROM snapshots").fetchone()[0],3)
            db.close()


if __name__=="__main__":unittest.main()
