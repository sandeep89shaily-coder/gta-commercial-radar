"""Four-city live stage acceptance: bounded results, honest blocks, 28-city merge."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gta_four_city_live_daily as live
import gta_28_city_combined as together
import gta_24_city_combined as legacy
from gta_24_city_ai_selection import candidates,finalize

DAY=dt.date(2026,11,19)
def write(path,fields,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
def source(city, n=1):
    return ([{
        "city":city,"application_id":f"SPA-2026-{n:04d}",
        "address":"99 Manufacturing Road",
        "scope":"New industrial manufacturing and logistics complex with equipment",
        "applicant":"Example Corporation",
        "stage":"UNDER REVIEW","category":"Industrial",
        "date":"2026-11-16",
        "date_basis":"APPLICATION_SUBMITTED_NOT_PUBLICATION",
        "source_url":"https://example.com/planning/file",
        "source_kind":"OFFICIAL_SOURCE",
    }],{"source":"https://example.com/planning/file"})

class FourCityLiveAndReconcile(unittest.TestCase):
    def test_independent_failures_and_fresh_first_seen(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def stub(city,**kwargs):
                if city=="Windsor":
                    raise PermissionError("ROBOTS_DISALLOWED")
                return source(city)
            outcome=live.run(root,collector=stub,today=DAY)
            self.assertEqual(outcome["cities_with_live_application_ids"],3)
            self.assertEqual(outcome["four_city_live_application_rows"],3)
            info={i["city"]:i for i in outcome["city_status"]}
            self.assertEqual(info["Windsor"]["retrieved_application_id_records"],0)
            self.assertIn("BLOCKED",info["Windsor"]["status"])
            self.assertFalse(outcome["all_four_live"])
            with (root/live.MASTER).open(encoding="utf-8-sig") as fp:
                rows=list(csv.DictReader(fp))
            self.assertEqual(len(rows),3)
            self.assertTrue(all(x["source_observation"]==
                "FIRST_OBSERVED_NOT_FIRST_PUBLICATION" for x in rows))
            old=live.run(root,collector=stub,today=DAY)
            with (root/live.MASTER).open(encoding="utf-8-sig") as fp:
                reused=list(csv.DictReader(fp))
            self.assertTrue(all(x["source_observation"]=="UNCHANGED"
                                for x in reused))
            self.assertEqual(old["verified_buyers"],0)
            self.assertFalse((root/"v5_ai_budget.sqlite").exists())

    def test_28_outputs_include_real_four_rows_and_keep_old_24(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for city in legacy.CITIES:
                pass
            base=[]
            for city in legacy.CITIES:
                row={k:"" for k in legacy.COLS}
                row.update({
                    "canonical_id":city.upper().replace(" ","_")+":FILE:TEST2026001",
                    "city":city,"cohort":"CORE_16" if city in legacy.CORE_CITIES
                      else "EXPANSION_8",
                    "record_kind":"APPLICATION","application_id":"TEST-2026-001",
                    "address":"100 Project Road",
                    "scope":"New industrial manufacturing complex with equipment and offices",
                    "current_status":"Under review",
                    "official_evidence_urls":"https://example.org/official/file",
                    "commercial_text_match":"True",
                    "source_date":"2024-01-01",
                })
                base.append(row)
            write(root/"GTA_RADAR_COMBINED_24_CITY_PROJECT_MASTER.csv",
                  legacy.COLS,base)
            write(root/"GTA_RADAR_COMBINED_24_CITY_COVERAGE.csv",
                  legacy.COVERAGE_COLS,[{"city":city} for city in legacy.CITIES])
            live.run(root,collector=lambda city,**kwargs:source(city),today=DAY)
            status=together.run(root,today=DAY)
            self.assertEqual(status["configured_city_count"],28)
            self.assertEqual(status["added_cities_with_live_application_ids"],4)
            self.assertEqual(status["all_four_added_city_source_rows"],4)
            with (root/together.MASTER).open(encoding="utf-8-sig") as fp:
                rows=list(csv.DictReader(fp))
            self.assertEqual(len(rows),28)
            with (root/together.COVERAGE).open(encoding="utf-8-sig") as fp:
                coverage=list(csv.DictReader(fp))
            self.assertEqual(len(coverage),28)
            top=candidates(root,universe=28,today=DAY)
            self.assertTrue(any(r["cohort"]=="ADDED_4" for r in top))
            result=finalize(root,today=DAY,universe=28)
            self.assertEqual(result["model_research_scope"],"COMBINED_28")
            self.assertTrue((root/"GTA_RADAR_COMBINED_28_CITY_TOP10.csv").exists())
            self.assertTrue((root/"GTA_RADAR_COMBINED_24_CITY_PROJECT_MASTER.csv").exists())

    def test_robots_fails_closed_and_no_network_in_mock(self):
        self.assertFalse(live.robots_allowed("http://example.com/"))
        self.assertFalse(live.robots_allowed("https://user:pass@example.org/a"))
        with self.assertRaises(live.SourceBlocked):
            live.fetch_html("https://other.org/file",
                            check_robots=True)
if __name__=="__main__":
    unittest.main()
