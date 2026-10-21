"""Automatic unlimited shortlist regression suite; no network or paid AI."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from commercial_opportunity_shortlist import qualify, source_scope
from commercial_lead_reports import build, read

NOW=dt.date(2026,10,21)
BASE={
 'project_id':'brampton_building_permits:26-123456-000-00',
 'source_id':'brampton_building_permits',
 'address':'100 Test Industrial Road, Brampton, ON','city':'Brampton',
 'official_verification_level':'OFFICIAL_ID_AND_STATUS_MATCH',
 'official_permit_id':'26-123456-000-00',
 'official_status':'Applied',
 'official_source_date':'2026-10-19',
 'official_record_url':'https://example.municipal.ca/permit/26-123456',
 'description':'New industrial warehouse expansion with loading dock and refrigeration equipment',
 'source_urls':'https://example.municipal.ca/permit/26-123456',
 'project_evidence_verified':'YES',
 'status':'AI_EVIDENCE_REVIEW'
}

def row(**fields):return dict(BASE,**fields)

def csv_write(path, records):
    cols=list(dict.fromkeys(k for rec in records for k in rec))
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(records)

class QualificationTests(unittest.TestCase):
    def test_live_industrial_application_passes_not_sale_ready(self):
        result=qualify(row(),today=NOW)
        self.assertEqual(result['qualification_group'],'PRIORITY_INVESTIGATION')
        self.assertIn('Industrial refrigeration',result['qualification_buyer_categories'])
        self.assertEqual(result['qualification_scope_basis'],'COLLECTOR_PROJECT_SCOPE')
        self.assertIn('Supplier availability',result['qualification_evidence_gaps'])
        self.assertGreaterEqual(int(result['qualification_score']),70)

    def test_unlimited_number_selected_without_35_or_any_maximum(self):
        rows=[row(project_id=f'brampton_building_permits:26-{i:06d}',
                  official_permit_id=f'26-{i:06d}') for i in range(100)]
        self.assertEqual(sum(qualify(x,today=NOW)['qualification_group']=='PRIORITY_INVESTIGATION'
                             for x in rows),100)

    def test_recent_local_exact_industrial_application_can_qualify(self):
        q=qualify(row(official_verification_level='COLLECTOR_SOURCE_MATCH',
                      official_status='Under Review'),today=NOW)
        self.assertEqual(q['qualification_group'],'PRIORITY_INVESTIGATION')
        self.assertEqual(q['qualification_confidence'],'LOCAL_EXACT_NOT_LIVE')
        self.assertIn('Live official status',q['qualification_evidence_gaps'])

    def test_undated_or_old_local_never_treated_as_timely(self):
        for date in ('','2024-01-01'):
            with self.subTest(date=date):
                q=qualify(row(official_verification_level='COLLECTOR_SOURCE_MATCH',
                              official_source_date=date),today=NOW)
                self.assertEqual(q['qualification_group'],'LIVE_STATUS_REFRESH_NEEDED')

    def test_web_story_at_same_address_not_exact_source(self):
        q=qualify(row(official_verification_level='',official_status='',
                      source_urls='https://old-building.example/renovation',
                      project_evidence_verified='YES'),today=NOW)
        self.assertEqual(q['qualification_group'],'EXACT_ID_VERIFICATION_NEEDED')

    def test_historical_record_not_priority(self):
        for status in ('Complete','Withdrawn','Cancelled','On Hold'):
            with self.subTest(status=status):
                q=qualify(row(official_status=status),today=NOW)
                self.assertEqual(q['qualification_group'],'HISTORICAL_OR_INACTIVE')

    def test_residential_house_and_health_inspections_excluded(self):
        a=qualify(row(description='New single detached dwelling second storey addition'),
                  today=NOW)
        b=qualify(row(source_id='peel_health_food',
                      description='Restaurant routine health food inspection'),today=NOW)
        self.assertEqual(a['qualification_group'],'RESIDENTIAL_OUTSIDE_SCOPE')
        self.assertEqual(b['qualification_group'],'NOT_COMMERCIAL_PROJECT_TRIGGER')

    def test_independent_restaurant_fitout_in_residential_complex_retained(self):
        q=qualify(row(description='Restaurant tenant fit-out within mixed-use residential building'),
                  today=NOW)
        self.assertEqual(q['qualification_group'],'PRIORITY_INVESTIGATION')
        self.assertIn('Commercial interior fit-out',q['qualification_buyer_categories'])

    def test_sign_only_is_separate(self):
        q=qualify(row(description='Retail shop signage installation on existing storefront'),
                  today=NOW)
        self.assertEqual(q['qualification_group'],'SMALL_SCOPE_SEPARATE_REVIEW')

    def test_relevant_ai_narrative_never_substitutes_missing_permit_scope(self):
        q=qualify(row(description='',official_description='',
                      project_stage='New $80 million factory proposed',
                      buyer_fit='Hypothesis only: industrial refrigeration contractors'),
                  today=NOW)
        self.assertEqual(q['qualification_group'],'ORIGINAL_SCOPE_NEEDED')
        self.assertEqual(q['qualification_scope'],'')

    def test_official_scope_takes_precedence_over_ai(self):
        x=row(description='Old office renovation summary',
              official_description='New industrial factory installation of refrigerant chillers')
        q=qualify(x,today=NOW)
        self.assertEqual(q['qualification_scope'],x['official_description'])
        self.assertEqual(q['qualification_scope_basis'],'LIVE_EXACT_OFFICIAL_SCOPE')

    def test_new_reports_preserve_every_old_row_and_no_api_spend(self):
        records=[
            row(project_id='brampton_building_permits:26-1',
                official_permit_id='26-1'),
            row(project_id='brampton_building_permits:26-2',
                official_permit_id='26-2',official_status='Complete'),
            row(project_id='toronto_active_building_permits:26 333333',
                official_permit_id='',official_status='',official_verification_level='',
                description='Industrial warehouse addition'),
            row(project_id='brampton_building_permits:26-4',
                official_permit_id='26-4',description=''),
        ]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            csv_write(root/'GTA_RADAR_V8_INVESTIGATIONS.csv',records)
            report=build(root)
            self.assertEqual(report['opportunity_review_records'],4)
            self.assertEqual(report['qualified_investigation_candidates'],1)
            self.assertEqual(report['opportunity_research_gaps'],3)
            self.assertEqual(len(read(root/'GTA_RADAR_GENUINE_OPPORTUNITY_REVIEW.csv')),4)
            self.assertEqual(len(read(root/'GTA_RADAR_OPPORTUNITY_RESEARCH_GAPS.csv')),3)
            self.assertEqual(len(read(root/'GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv')),1)
            self.assertTrue((root/'GTA_RADAR_SHORTLIST.html').is_file())
            self.assertIn('NOT verified open supplier contracts',
                          (root/'GTA_RADAR_SHORTLIST.html').read_text(encoding='utf-8'))
            self.assertTrue(all(r['sale_ready']=='NO'
                for r in read(root/'GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv')))

if __name__=='__main__':
    unittest.main()
