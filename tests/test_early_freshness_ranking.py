"""Regression: uploaded desktop run had top 50 Brampton files from 2019.
Require recent genuine source date or application receipt before shortlist.
"""
import datetime as dt
import unittest
import early_pilot_summary as summary

TODAY=dt.date(2026,10,24)

def sample(sid,ident,city="BRAMPTON",site="100 Industrial Drive",title="New industrial warehouse",app="",published=""):
    return dict(source_id=sid,item_id=ident,city=city,site=site,title=title,
      application_date=app,official_public_posting_date=published,
      published_entity="Public business applicant",
      record_url="https://www.example.ca/project/"+ident,
      lead_status="NOT_SALE_READY_RESEARCH_ONLY",radar_first_seen="2026-10-24",
      commercial_signal="POSSIBLE_COMMERCIAL")

class Tests(unittest.TestCase):
    def test_historical_preconsultation_excluded_even_if_long_title(self):
        old=sample("brampton_preconsultation","old",app="2019-08-29",
                   title="Site Plan for one-storey industrial warehouse with an accessory office")
        self.assertEqual(summary.preview_candidates([old],today=TODAY),[])
        self.assertEqual(summary.priority(old,TODAY)[1],
           "HISTORICAL_OR_NO_VERIFIED_RECENT_PROJECT_DATE")

    def test_recent_city_notice_outranks_undated_and_recent_received(self):
        old=sample("brampton_preconsultation","old",app="2019-08-29")
        received=sample("brampton_preconsultation","received",app="2026-10-16")
        published=sample("hamilton_planning_notices","published","HAMILTON",
                "925 Main Street West",title="New commercial building application",
                published="2026-10-19")
        result=summary.preview_candidates([old,received,published],today=TODAY)
        self.assertEqual([x["item_id"] for x in result],["published","received"])
        self.assertIn("RECEIPT_NOT_PUBLICATION",result[1]["why_research"])
        self.assertEqual(result[0]["public_posting_date"],"2026-10-19")

    def test_ontario_wide_unlocated_ero_not_gta_lead(self):
        ero=sample("ero_proposal_watch","water",city="",site="",published="2026-10-22")
        self.assertEqual(summary.preview_candidates([ero],today=TODAY),[])

    def test_first_seen_today_never_makes_old_app_new(self):
        old=sample("toronto_development","old",city="TORONTO",app="2020-10-17")
        old["radar_first_seen"]="2026-10-24T22:00:00"
        self.assertEqual(summary.preview_candidates([old],today=TODAY),[])

    def test_no_future_dates(self):
        future=sample("pickering_proposals","future",city="PICKERING",published="2026-12-30")
        self.assertEqual(summary.preview_candidates([future],today=TODAY),[])

if __name__=="__main__":
    unittest.main()
