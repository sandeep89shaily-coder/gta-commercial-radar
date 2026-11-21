"""Official announcements: preserve publisher dates, first-seen evidence,
source outages, dedup, and do not turn old grants or news into open orders.
"""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_official_industrial_announcement_monitor import (
    run, LEDGER, FRESH, HISTORY,
)
from gta_freshness_first_daily_selection import (
    run as select, EQUIPMENT_TOP,
)

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Ontario</title>
<item><title>Ontario welcomes Ford manufacturing plant retooling and expansion</title>
<link>https://news.ontario.ca/en/release/1008308/ford-investment</link>
<pubDate>Fri, 20 Nov 2026 09:00:00 -0500</pubDate>
<description>Oakville automaker will invest to retool plant, add automation and production line equipment.</description></item>
<item><title>Old industrial manufacturing investment</title>
<link>https://news.ontario.ca/en/release/999999/old-plant</link>
<pubDate>Mon, 19 Oct 2026 09:00:00 -0500</pubDate>
<description>Factory expansion and machinery modernization in Mississauga.</description></item>
<item><title>Ontario launches funding information portal</title>
<link>https://news.ontario.ca/en/release/00000/portal</link>
<pubDate>Fri, 20 Nov 2026 09:00:00 -0500</pubDate>
<description>General policy updates for the public.</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>FedDev Ontario backs new precision manufacturing equipment in Windsor</title>
<link rel="alternate" href="https://feddev-ontario.canada.ca/en/media-room/precision"/>
<published>2026-11-19T13:30:00-05:00</published>
<summary>Windsor manufacturer invests in CNC machinery to expand industrial capacity.</summary></entry>
</feed>"""

def csvrows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

class AnnouncementMonitorTests(unittest.TestCase):
    def test_multi_feed_first_seen_and_old_history(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            urls={"rss":"https://news.ontario.ca/newsroom/en/rss/allnews.rss",
                  "atom":"https://api.io.canada.ca/some-feed"}
            def fetch(url):
                return (RSS if url==urls["rss"] else ATOM).encode("utf-8")
            first=run(root,today=dt.date(2026,11,21),fetcher=fetch,feeds=urls)
            self.assertEqual(first["recent_publisher_dated_research"],2)
            self.assertEqual(first["historical_observed"],1)
            self.assertEqual(first["verified_open_supplier_packages"],0)
            candidates=csvrows(root/FRESH)
            self.assertEqual({x["city_mentioned"] for x in candidates},{"Oakville","Windsor"})
            self.assertTrue(all(x["publication_independently_verified"]=="False" for x in candidates))
            selected=select(root,today=dt.date(2026,11,21))
            self.assertEqual(selected["equipment_top10_count"],2)
            self.assertTrue(all(x["open_supplier_package_verified"]=="False"
                                for x in csvrows(root/EQUIPMENT_TOP)))
            ledger=json.loads((root/LEDGER).read_text())
            self.assertEqual(len(ledger["records"]),3)
            repeated=run(root,today=dt.date(2026,11,22),fetcher=fetch,feeds=urls)
            self.assertEqual(repeated["ledger_unique_urls"],3)
            self.assertEqual({x["observation"] for x in csvrows(root/FRESH)},{"UNCHANGED"})
            self.assertEqual({x["first_seen_by_radar"] for x in csvrows(root/FRESH)},{"2026-11-21"})

    def test_feed_outage_preserves_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            url="https://news.ontario.ca/newsroom/en/rss/allnews.rss"
            run(root,today="2026-11-21",fetcher=lambda _:RSS.encode(),feeds={"rss":url})
            before=(root/LEDGER).read_bytes()
            def offline(_):raise OSError("network down")
            result=run(root,today="2026-11-22",fetcher=offline,feeds={"rss":url})
            self.assertEqual(result["sources_collected"],0)
            self.assertEqual((root/LEDGER).read_bytes(),before)
            self.assertEqual(csvrows(root/FRESH),[])

    def test_undated_atom_updated_is_not_publication(self):
        xml=b"""<feed xmlns="http://www.w3.org/2005/Atom">
            <entry><title>Ontario factory expansion</title>
            <link href="https://www.canada.ca/old" />
            <updated>2026-11-21T09:00:00Z</updated>
            <summary>Manufacturing investment equipment</summary></entry></feed>"""
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            result=run(root,today="2026-11-21",fetcher=lambda _:xml,feeds={"x":"https://api.io.canada.ca/x"})
            self.assertEqual(result["recent_publisher_dated_research"],0)
            self.assertEqual(result["ledger_unique_urls"],0)

if __name__=="__main__": unittest.main()
