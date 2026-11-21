"""Forty-entry FedDev run never drops dated, undated or nonindustrial rows."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from gta_feddev_all40_audit import run,REPORT,EVIDENCE,STATUS
from gta_freshness_first_daily_selection import run as select,EQUIPMENT_TOP
from gta_industrial_fulltext_discovery import INDEXES

ATOM_NS="http://www.w3.org/2005/Atom"
def feed(n):
    entries=[]
    for i in range(1,n+1):
        url=("https://www.canada.ca/en/economic-development-southern-ontario/"
             "news/2026/11/manufacturing-expansion-"+str(i)+".html")
        entries.append(
            "<entry><title>FedDev 2026 manufacturer release "+str(i)+"</title>"
            "<link href='"+url+"' rel='alternate'/><updated>2026-11-21T01:00:00Z</updated></entry>")
    return ('<feed xmlns="'+ATOM_NS+'">'+"".join(entries)+"</feed>").encode()

def article(number):
    # Two recent, one undated, one completed, the rest historical.
    date="2026-11-20" if number in (1,2,4) else "2026-09-10"
    if number==3: date=""
    headline="<h1>Southern Ontario Manufacturing announcement</h1>"
    meta=('<meta property="article:published_time" content="'+date+'"/>') if date else ""
    body=(
        "A manufacturer in London will invest in CNC machinery to expand its factory production line."
        if number in (1,2,3) else
        "Factory retooling is complete. Manufacturing equipment is installed and production has begun."
        if number==4 else
        "An Ontario factory will expand production capacity with industrial equipment."
    )
    return ("<html><head>"+meta+"</head><body>"+headline+
            "<article><p>"+body+" More information about this manufacturing initiative "
            "is available to businesses across Ontario.</p></article></body></html>").encode()

def csvrows(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))

class FedDevForty(unittest.TestCase):
    def test_all_40_individually_audited_and_new_dated_fresh_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            feed_url=INDEXES["FEDDEV_OFFICIAL_2026_ARCHIVE"]
            received=[]
            def fetch(url):
                received.append(url)
                if url==feed_url:return feed(40)
                n=int(url.rsplit("-",1)[-1].split(".")[0])
                return article(n)
            result=run(root,today="2026-11-21",fetcher=fetch)
            self.assertEqual(result["atom_agency_entries"],40)
            self.assertEqual(result["rows_written"],40)
            self.assertEqual(result["full_articles_fetched"],40)
            self.assertEqual(result["network_requests_max"],41)
            self.assertEqual(len(received),41)
            self.assertEqual(result["recent_publisher_dated"],3)
            rows=csvrows(root/REPORT)
            self.assertEqual(len(rows),40)
            self.assertEqual(rows[2]["article_reported_date"],"")
            self.assertEqual(rows[2]["freshness_classification"],"UNKNOWN_PUBLICATION_DATE_HOLD")
            self.assertEqual(rows[3]["procurement_stage"],"COMPLETED_OR_OPERATIONAL_NOT_UPCOMING_ORDER")
            self.assertTrue(all(r["purchasing_contact_verified"]=="False" for r in rows))
            self.assertTrue(all(r["open_equipment_order_verified"]=="False" for r in rows))
            self.assertEqual(len(json.loads((root/EVIDENCE).read_text())["articles"]),40)
            self.assertTrue((root/STATUS).is_file())
            selected=select(root,today="2026-11-21")
            self.assertEqual(selected["equipment_top10_count"],3)
            self.assertTrue(all(r["open_supplier_package_verified"]=="False"
                                for r in csvrows(root/EQUIPMENT_TOP)))
            run(root,today="2026-11-22",fetcher=fetch)
            self.assertTrue(all(r["first_seen_by_radar"]=="2026-11-21"
                                for r in csvrows(root/REPORT)))

    def test_failure_retains_one_row_per_entry_without_false_success(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            feed_url=INDEXES["FEDDEV_OFFICIAL_2026_ARCHIVE"]
            def fetch(url):
                if url==feed_url:return feed(40)
                if url.endswith("11.html"):raise OSError("read timeout")
                return article(1)
            result=run(root,today="2026-11-21",fetcher=fetch)
            self.assertEqual(result["rows_written"],40)
            self.assertEqual(result["fetch_failures"],1)
            row=csvrows(root/REPORT)[10]
            self.assertEqual(row["article_retrieval_status"],"FAILED_OSError")
            self.assertEqual(row["published_in_last_7_days"],"UNKNOWN")

    def test_enforces_bound(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                run(Path(d),limit=41)

if __name__=="__main__":unittest.main()
