"""V6 source-research regression cases: no invented evidence or AI claims."""
import datetime as dt
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import v6_daily_pipeline as v6


class V6EvidenceRepairTests(unittest.TestCase):
    def test_address_abbreviation_and_exact_match(self):
        record={'address':'1430 BIRCHMOUNT RD, Toronto','company_name':'UNKNOWN',
                'source_keys':'25249692ESC21CD'}
        self.assertTrue(v6.evidence_matches(record,'Development at 1430 Birchmount Road, Toronto'))
        self.assertFalse(v6.evidence_matches(record,'Unrelated property at 1420 Birchmount Road'))

    def test_search_results_without_pages_not_verified(self):
        with patch.dict(sys.modules,{'v5_investigator':SimpleNamespace(search_rss=None)}):
            pages,attempts=v6.discover_improved(
                {'address':'622 Fogal Rd, Brampton'},
                search=lambda query:['https://example.org/unrelated'],
                fetch=lambda url:'Another property',max_searches=2)
        self.assertEqual(pages,[])
        self.assertEqual(attempts,2)

    def test_official_record_identifier_can_match(self):
        self.assertTrue(v6.evidence_matches(
            {'address':'','source_keys':'25249692ESC21CD','company_name':'UNKNOWN'},
            'City application 25249692ESC21CD.'))

    def test_failed_evidence_retry_next_day(self):
        stub=SimpleNamespace(CLOSED=v6.re.compile(r'closed',v6.re.I))
        records=[{'project_id':'failed','lane':'PERMIT_REVIEW','review_priority':'55'},
                 {'project_id':'succeeded','lane':'PERMIT_REVIEW','review_priority':'50'}]
        previous={'failed':{'researched_at':'2026-10-18T08:00:00','status':'NO_CORROBORATED_PAGE'},
                  'succeeded':{'researched_at':'2026-10-18T08:00:00','status':'AI_EVIDENCE_REVIEW'}}
        with patch.dict(sys.modules,{'v5_investigator':stub}):
            with patch.object(v6,'v5_original_queue',lambda rows,n,previous,day:rows):
                self.assertEqual(v6.select_unresearched(records,25,previous,dt.date(2026,10,18)),[])
                next_day=v6.select_unresearched(records,25,previous,dt.date(2026,10,19))
        self.assertEqual([r['project_id'] for r in next_day],['failed'])

    def test_permit_before_historical_update(self):
        stub=SimpleNamespace(CLOSED=v6.re.compile(r'withdrawn',v6.re.I))
        records=[{'project_id':'change','lane':'SOURCE_UPDATE_WATCH','review_priority':'90'},
                 {'project_id':'permit','lane':'PERMIT_REVIEW','review_priority':'60'},
                 {'project_id':'planning','lane':'PLANNING_WATCH','review_priority':'70'}]
        with patch.dict(sys.modules,{'v5_investigator':stub}):
            with patch.object(v6,'v5_original_queue',lambda rows,n,previous,day:rows):
                selected=v6.select_unresearched(records,2,{},dt.date(2026,10,18))
        self.assertEqual([r['project_id'] for r in selected],['planning','permit'])


if __name__=='__main__':unittest.main()
