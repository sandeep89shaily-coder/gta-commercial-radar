"""Eight-city municipality source monitoring, link provenance and AI routing tests."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

import gta_daily_intelligence as daily
from gta_early_signal_feed_monitor import FEEDS, collect
from municipal_meeting_capture import OFFICIAL, discover
from tests.test_daily_integrated_intelligence import DailyIntegrationTests, TODAY


CITIES={"Toronto","Brampton","Mississauga","Hamilton",
        "Burlington","Oakville","Vaughan","Kitchener"}


class EightCityTests(unittest.TestCase):
    def test_official_city_indexes_registered(self):
        self.assertEqual(set(OFFICIAL),CITIES)
        self.assertEqual(len(set(OFFICIAL.values())),8)
        self.assertTrue(CITIES<={
            "Toronto" if k=="toronto_council" else
            "Mississauga" if k=="mississauga_council" else
            "Hamilton" if k=="hamilton_planning" else
            "Oakville" if k=="oakville_agendas" else
            "Vaughan" if k=="vaughan_council" else
            "Kitchener" if k=="kitchener_council" else
            "Burlington" if k=="burlington_agendas" else
            "Brampton" if k=="brampton_planning" else ""
            for k in FEEDS
        })

    def test_discover_official_agenda_links_but_never_calls_them_projects(self):
        markup = ('<a href="/council/planning-agenda-2026">Planning agenda and staff reports</a>'
                  '<a href="/council/planning-agenda-2026">Same duplicate</a>'
                  '<a href="https://evil.example/agendas">External agenda</a>')
        for city in CITIES:
            with self.subTest(city=city):
                r=discover(city,fetch=lambda _:markup)
                self.assertEqual(r["official_index_status"],"INDEX_FETCHED_LINK_ONLY")
                self.assertEqual(r["agenda_links_discovered"],1)
                self.assertEqual(r["documents_retrieved"],0)
                self.assertEqual(r["publication_dates_verified"],0)
                self.assertEqual(r["discovered"],0)
                url=r["agenda_candidates"][0]["url"]
                self.assertTrue(url.startswith("https://"))
                self.assertNotIn("evil.example",url)
                self.assertEqual(r["agenda_candidates"][0]["status"],
                                 "OFFICIAL_INDEX_LINK_ONLY_PUBLICATION_DATE_UNKNOWN")

    def test_early_feed_isolated_per_municipal_official_hostname(self):
        with tempfile.TemporaryDirectory() as t:
            report=collect(t,transport=lambda _:
                           '<a href="https://www.vaughan.ca/meetings/agenda">Agenda</a>')
            self.assertEqual(len([v for v in report["candidate_links"]
                                  if v["feed"]=="vaughan_council"]),1)
            self.assertTrue(all(v["feed"]=="vaughan_council"
                                for v in report["candidate_links"]))
            self.assertTrue(all(not v["publication_date_verified"]
                                for v in report["candidate_links"]))

    def test_daily_integration_emits_new_agenda_link_once_and_does_not_pay_for_link(self):
        # Reuse the offline integrated collector mocks; no external I/O.
        test=DailyIntegrationTests(methodName="test_daily_integrates_municipal_sources_doc_research_and_buyer_worklist")
        test.setUp()
        try:
            def meeting(city,out,**kw):
                out=Path(out);out.mkdir(parents=True,exist_ok=True)
                manifest=out/(city.upper()+"_MEETINGS.json")
                agenda=[{"url":"https://www.vaughan.ca/council/public-planning-report",
                         "title":"New industrial development planning agenda"}] if city=="Vaughan" else []
                manifest.write_text(json.dumps({"agenda_candidates":agenda}),encoding="utf-8")
                return {"city":city,"meeting_index":str(manifest),
                        "agenda_links_discovered":len(agenda)}
            test.meeting=meeting
            first=test.execute(paid=False)
            self.assertEqual(first["municipal_official_index_count"],8)
            self.assertEqual(first["new_municipal_agenda_links_for_review"],1)
            self.assertEqual(first["meeting_documents_fetched_outside_toronto"],0)
            rows=daily._csv(first["combined_csv"])
            candidates=[r for r in rows if r["kind"]=="MUNICIPAL_AGENDA_LINK_REVIEW"]
            self.assertEqual(len(candidates),1)
            self.assertEqual(candidates[0]["source_date"],"")
            self.assertEqual(candidates[0]["date_basis"],"RADAR_OBSERVED_NOT_PUBLISHER_DATE")
            self.assertEqual(candidates[0]["project_id"],"")
            self.assertIn("THEN_AI",candidates[0]["ai_next_step"])
            self.assertFalse(any(x[0] in ("project_ai","buyer_ai")
                                 for x in test.calls))
            again=test.execute(paid=False)
            self.assertEqual(again["new_municipal_agenda_links_for_review"],0)
            self.assertEqual(len(daily._json(test.root/daily.MEETING_LINK_LEDGER)),1)
        finally:
            test.doCleanups()


if __name__=="__main__":
    unittest.main()
