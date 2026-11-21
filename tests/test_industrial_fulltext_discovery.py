"""End-to-end public publisher full-text announcements with mock HTML/Atom.

Tests refuse historical old articles, show government-wide FedDev fallback
agency filtering, correct full text timing and prevent fabricated buyer claims.
"""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from gta_industrial_fulltext_discovery import run,FILES,GOVERNMENT_ATOM
from gta_freshness_first_daily_selection import run as select,EQUIPMENT_TOP

ATOM=b"""<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Ontario manufacturer builds new CNC production plant</title>
<link href="https://www.canada.ca/en/economic-development-southern-ontario/news/2026/11/ontario-manufacturing-capacity.html"/>
<published>2026-11-20T13:00:00-05:00</published>
<summary>London manufacturer will invest to expand production machinery capacity.</summary></entry>
<entry><title>Other agency manufacturing plant investment</title>
<link href="https://www.canada.ca/en/innovation-science-economic-development/news/2026/11/industry-announcement.html"/>
<published>2026-11-20T13:00:00-05:00</published>
<summary>Factory manufacturing modernization equipment.</summary></entry>
</feed>"""
FEDDEV=b"""<html><head><meta property="article:published_time" content="2026-11-20T12:00:00-05:00"></head>
<body><h1>Ontario manufacturer builds new CNC production plant</h1>
<article>On November 20, 2026 in London, Ontario, an industrial manufacturer plans to
invest in CNC machinery for a factory expansion and expects to install production line equipment next year.</article></body></html>"""
LINAMAR_INDEX=b"""<html><body><a href="/news/guelph-industrial-robotic-expansion/">
Linamar plans manufacturing robotics expansion</a>
<a href="/about/">About company</a></body></html>"""
LINAMAR=b"""<html><body><h1>Linamar plans manufacturing robotics expansion</h1>
<time datetime="2026-11-19">November 19, 2026</time><article>
Linamar plans to expand its manufacturing production with an industrial robot cell in Guelph.
The firm will install robotics in a new production line.</article></body></html>"""
INVEST_INDEX=b"""<html><body>
<a href="/news/hitachi-2026-plant">Hitachi Energy new manufacturing plant investment in London</a>
</body></html>"""
INVEST_ARTICLE=b"""<html><body><h1>Hitachi Energy builds new manufacturing plant London</h1>
<time datetime="2026-10-16">October 16, 2026</time>
<article>Hitachi Energy will build a transformer insulation production facility
in London, Ontario and expects to add machinery.</article></body></html>"""
COMPLETE=b"""<html><head><meta property="article:published_time" content="2026-11-20"/></head><body>
<h1>Industrial manufacturing expansion</h1><article>Factory retooling is complete.
The plant has begun production with its installed manufacturing equipment in London.</article>
</body></html>"""

def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

class FullTextTests(unittest.TestCase):
    def test_feddev_fallback_company_and_investment_dates(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            index={"FEDDEV_GOVERNMENT_WIDE_ATOM":GOVERNMENT_ATOM,
                   "LINAMAR":"https://www.linamar.com/news-listings/",
                   "INVEST_ONTARIO":"https://investontario.ca/press-room"}
            pages={GOVERNMENT_ATOM:ATOM,
              index["LINAMAR"]:LINAMAR_INDEX,
              index["INVEST_ONTARIO"]:INVEST_INDEX,
              "https://www.canada.ca/en/economic-development-southern-ontario/news/2026/11/ontario-manufacturing-capacity.html":FEDDEV,
              "https://www.linamar.com/news/guelph-industrial-robotic-expansion/":LINAMAR,
              "https://investontario.ca/news/hitachi-2026-plant":INVEST_ARTICLE}
            result=run(root,today="2026-11-21",fetcher=lambda u:pages[u],indexes=index)
            self.assertEqual(result["recent_dated_research"],2)
            self.assertEqual(result["older_watchlist"],1)
            self.assertEqual(result["federal_fallback_observed_feddev_articles"],1)
            fresh=rows(root/FILES["fresh"])
            self.assertEqual({x["source"] for x in fresh},
                             {"FEDDEV_GOVERNMENT_WIDE_ATOM","LINAMAR"})
            self.assertTrue(all(x["open_supplier_package_verified"]=="False" for x in fresh))
            selection=select(root,today="2026-11-21")
            self.assertEqual(selection["equipment_top10_count"],2)
            self.assertEqual(len(rows(root/EQUIPMENT_TOP)),2)
            before=json.loads((root/FILES["ledger"]).read_text())["records"]
            again=run(root,today="2026-11-22",fetcher=lambda u:pages[u],indexes=index)
            self.assertEqual(again["ledger_total_urls"],3)
            after=json.loads((root/FILES["ledger"]).read_text())["records"]
            self.assertEqual({x["first_seen_by_radar"] for x in after.values()},{"2026-11-21"})
            self.assertEqual({x["observation"] for x in rows(root/FILES["fresh"])},{"UNCHANGED"})

    def test_completed_plant_not_labelled_open_equipment(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            url="https://www.linamar.com/news/industrial-expansion/"
            res=run(root,today="2026-11-21",
                indexes={"LINAMAR":"https://www.linamar.com/news-listings/"},
                fetcher=lambda u:(LINAMAR_INDEX.replace(b"/news/guelph-industrial-robotic-expansion/",
                                                        b"/news/industrial-expansion/")
                                  if "news-listings" in u else COMPLETE))
            item=rows(root/FILES["fresh"])[0]
            self.assertEqual(item["procurement_stage"],
                             "COMPLETED_OR_OPERATIONAL_NOT_UPCOMING_ORDER")
            self.assertEqual(item["open_supplier_package_verified"],"False")

    def test_failed_source_does_not_erase_historical_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);url="https://www.linamar.com/news-listings/"
            run(root,today="2026-11-21",indexes={"LINAMAR":url},
                fetcher=lambda u:LINAMAR_INDEX if u==url else LINAMAR)
            original=(root/FILES["ledger"]).read_bytes()
            def fail(u):raise OSError("blocked")
            result=run(root,today="2026-11-22",indexes={"LINAMAR":url},fetcher=fail)
            self.assertEqual(result["sources"]["LINAMAR"]["status"],"INDEX_FAILED")
            self.assertEqual((root/FILES["ledger"]).read_bytes(),original)
            self.assertEqual(result["recent_dated_research"],0)

if __name__=="__main__":unittest.main()
