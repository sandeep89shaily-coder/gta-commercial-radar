"""Regression cases for exact-permit lifecycle and realistic buyer opportunity screening."""
from __future__ import annotations
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

from opportunity_lifecycle import assess, classify_status, identity_of_page
import commercial_lead_reports as reports
import v8_ai_queue as queue
import v8_deepseek_native as native

TODAY=dt.date(2026,10,21)
BASE={'project_id':'toronto_active_building_permits:26 214321',
      'source_id':'toronto_active_building_permits',
      'source_keys':'26 214321 BLD|00',
      'address':'125 King Street West','city':'Toronto',
      'description':'Industrial tenant fit-out including refrigeration',
      'source_record_date':'2026-10-18','current_source_status':'Under Review'}

def write_csv(path, rows):
    fields=list(dict.fromkeys(k for row in rows for k in row)) if rows else ['project_id']
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

class LifecycleTests(unittest.TestCase):
    def test_exact_status_is_not_a_sale(self):
        for status,expected,op in [
            ('Applied','PRE_APPROVAL','EARLY_STAGE_PROJECT_REVIEW'),
            ('Application Acceptable','APPROVED_NOT_ISSUED','APPROVED_STAGE_REVIEW'),
            ('Issuance Pending','PRE_ISSUANCE','PRE_ISSUANCE_REVIEW'),
            ('Issued Permit','PERMIT_ISSUED','ISSUED_PERMIT_TIMING_CHECK'),
            ('Revision Issued','PERMIT_ISSUED','ISSUED_PERMIT_TIMING_CHECK'),
            ('Inspection','INSPECTION_STAGE','INSPECTION_STAGE_WORK'),
            ('Complete','COMPLETED','HISTORICAL_OR_INACTIVE'),
            ('Application On Hold','BLOCKED_OR_INACTIVE','HISTORICAL_OR_INACTIVE'),
            ('Appeal Received by TLAB','BLOCKED_OR_INACTIVE','HISTORICAL_OR_INACTIVE')]:
            with self.subTest(status=status):
                result=assess(BASE,dict(official_verification_level='OFFICIAL_ID_AND_STATUS_MATCH',
                                    official_status=status,
                                    official_checked_at='2026-10-21T13:00:00Z'),today=TODAY)
                self.assertEqual(result['lifecycle_stage'],expected)
                self.assertEqual(result['opportunity_class'],op)
                self.assertEqual(result['supplier_contract_status'],'NOT_ESTABLISHED')
                self.assertNotIn('AVAILABLE',result['supplier_contract_status'])

    def test_inspection_does_not_prove_open_subcontracting(self):
        x=assess(BASE,dict(official_verification_level='OFFICIAL_ID_AND_STATUS_MATCH',
                          official_status='Inspection'),today=TODAY)
        self.assertEqual(x['opportunity_class'],'INSPECTION_STAGE_WORK')
        self.assertIn('remaining trades',x['opportunity_next_action'])

    def test_historical_or_local_status_requires_refresh(self):
        r=dict(BASE,source_record_date='2025-12-01')
        x=assess(r,dict(official_status='Permit Issued',
                        official_verification_level='COLLECTOR_SOURCE_MATCH'),today=TODAY)
        self.assertEqual(x['opportunity_class'],'STATUS_REFRESH_REQUIRED')
        self.assertEqual(x['lifecycle_status_basis'],'EXACT_COLLECTOR_SNAPSHOT_NOT_LIVE')
        self.assertGreater(int(x['lifecycle_source_age_days']),90)

    def test_observation_date_never_becomes_permit_issuance(self):
        r=dict(BASE,source_record_date='',event_date='2026-10-20',
               event_date_basis='CHANGE_DETECTED_NOT_ISSUED',
               current_source_status='Revision Issued')
        x=assess(r,dict(official_verification_level='OFFICIAL_ID_AND_STATUS_MATCH',
                        official_status='Revision Issued'),today=TODAY)
        self.assertEqual(x['lifecycle_source_date'],'')
        self.assertNotIn('ISSUANCE',x['lifecycle_status_basis'])

    def test_same_address_different_permit_is_not_same_project(self):
        other='Renovation and substantial completion at 125 King Street West, Toronto, permit 20 125432 BLD'
        self.assertEqual(identity_of_page(BASE,other),'DIFFERENT_PERMIT_ID_AT_ADDRESS')
        exact='Toronto permit 26 214321 BLD is in the application review stage'
        self.assertEqual(identity_of_page(BASE,exact),'EXACT_CURRENT_PERMIT_ID_IN_PAGE')
        generic='Work on 125 King Street West Toronto building constructed in 2019'
        self.assertEqual(identity_of_page(BASE,generic),'ADDRESS_CONTEXT_UNCONFIRMED')
        x=assess(BASE,{'source_urls':'https://example.ca/old-building'},today=TODAY)
        self.assertEqual(x['opportunity_class'],'EXACT_PROJECT_VERIFICATION_NEEDED')
        self.assertEqual(x['project_identity_confidence'],'ADDRESS_CONTEXT_ONLY')

    def test_claimed_roles_not_awarded_contracts(self):
        x=assess(BASE,{
            'official_verification_level':'OFFICIAL_ID_AND_STATUS_MATCH',
            'official_status':'Applied',
            'official_company':'Example Construction Ltd',
            'official_company_role':'builder',
            'operator':'Proposed Grocery Tenant',
            'contractor':'Unverified Construction Inc',
            'project_stage':'This major redevelopment finished in 2015',
        },today=TODAY)
        self.assertEqual(x['company_builder'],'Example Construction Ltd')
        self.assertEqual(x['company_applicant'],'')
        self.assertEqual(x['company_operator_claim'],'Proposed Grocery Tenant')
        self.assertEqual(x['company_contractor_claim'],'Unverified Construction Inc')
        self.assertEqual(x['supplier_contract_status'],'NOT_ESTABLISHED')
        self.assertEqual(x['lifecycle_stage'],'PRE_APPROVAL')
        self.assertNotEqual(x['lifecycle_stage'],'COMPLETED')

    def test_broad_historical_report_reclassified_without_ai_cost(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            rows=[
                dict(project_id='toronto_active_building_permits:24 121212',
                     source_id='toronto_active_building_permits',
                     address='100 Queen Street West',description='Office fit-out',
                     status='AI_EVIDENCE_REVIEW',source_urls='https://developer.example/old',
                     project_evidence_verified='YES'),
                dict(project_id='brampton_building_permits:B-102',
                     source_id='brampton_building_permits',source_keys='B-102',
                     address='100 McLaughlin Rd',description='Industrial unit expansion',
                     official_verification_level='OFFICIAL_ID_AND_STATUS_MATCH',
                     official_status='Issued',official_source_date='2026-10-15',
                     status='AI_EVIDENCE_REVIEW',
                     source_urls='https://municipal.example/permit/B-102',
                     project_evidence_verified='YES'),
                dict(project_id='toronto_active_building_permits:24 010101',
                     source_id='toronto_active_building_permits',status='AI_SOURCE_RECORD_REVIEW',
                     address='500 Unknown Road',description='Warehouse alteration',
                     project_evidence_verified='NO')
            ]
            write_csv(root/'GTA_RADAR_V8_INVESTIGATIONS.csv',rows)
            summary=reports.build(root)
            self.assertEqual(summary['opportunity_review_records'],3)
            review=reports.read(root/'GTA_RADAR_GENUINE_OPPORTUNITY_REVIEW.csv')
            by_id={r['project_id']:r for r in review}
            self.assertEqual(by_id[rows[0]['project_id']]['opportunity_class'],
                             'EXACT_PROJECT_VERIFICATION_NEEDED')
            self.assertEqual(by_id[rows[1]['project_id']]['opportunity_class'],
                             'ISSUED_PERMIT_TIMING_CHECK')
            self.assertEqual(by_id[rows[2]['project_id']]['sale_ready'],'NO')
            self.assertEqual(summary['project_opportunities'],2)
            self.assertEqual(summary['issued_stage_review'],1)
            self.assertIn('GTA_RADAR_GENUINE_OPPORTUNITY_REVIEW.csv',
                          (root/'GTA_RADAR_LEAD_INTELLIGENCE.html').read_text())

    def test_old_address_only_research_stays_queued(self):
        row=dict(BASE,lane='PERMIT_REVIEW',review_priority='83')
        history={row['project_id']:{
            'status':'AI_EVIDENCE_REVIEW','project_evidence_verified':'YES',
            'input_fingerprint':queue.fingerprint(row),
            'investigated_local_date':'2026-10-15'}}
        pending=queue.build([row],[],history,TODAY)
        self.assertEqual(len(pending),1)
        self.assertEqual(len(queue.due(pending,history,TODAY)),0)
        self.assertEqual(len(queue.due(pending,history,TODAY+dt.timedelta(days=2))),1)

    def test_early_stage_ranks_before_inspection_within_permit_queue(self):
        inspected=dict(BASE,project_id='A',current_source_status='Inspection',
                       _queued_on='2026-10-01',lane='PERMIT_REVIEW',review_priority='83')
        applied=dict(BASE,project_id='B',current_source_status='Under Review',
                     _queued_on='2026-10-20',lane='PERMIT_REVIEW',review_priority='83')
        self.assertEqual(queue.due([inspected,applied],{},TODAY)[0]['project_id'],'B')

    def test_deepseek_budget_unchanged(self):
        self.assertEqual(native.DAILY_LIMIT,0.49)

if __name__=='__main__':
    unittest.main()
