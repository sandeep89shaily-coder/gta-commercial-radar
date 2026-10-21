"""Cross-layer tests for the user-observed V8 lead-selection failures."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

import commercial_research_policy as policy
import commercial_selector_v4 as selector
import v8_ai_queue as queue
import v8_deepseek_native as ai
import commercial_lead_reports as reports


def permit(index=1,**extras):
    x={'source_id':'toronto_active_building_permits',
       'source_key':f'26 {index:06d} BLD|00',
       'description':'Interior alterations for a commercial office fit-out',
       'address':f'{120+index} Front St W','city':'Toronto',
       'source_group':'MUNICIPAL_CHANGE','event_date':'2026-10-19',
       'event_date_basis':'CHANGE_DETECTED_NOT_PERMIT_ISSUED','company_name':''}
    x.update(extras);return x


def write_csv(path,rows):
    keys=list(dict.fromkeys(k for x in rows for k in x))
    with Path(path).open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=keys);writer.writeheader();writer.writerows(rows)


class CommercialPipelinePolicyTests(unittest.TestCase):
    def test_unchanged_permit_source_event_is_priority_but_not_issued(self):
        row=permit()
        self.assertEqual(selector.classify(row)[0],'PERMIT_REVIEW')
        result=selector.summarize([row],{})
        self.assertEqual(result['research_route'],'AI_PRIORITY')
        self.assertGreaterEqual(result['review_priority'],70)
        self.assertIn('NOT ISSUANCE',result['date_basis'])

    def test_inspections_are_enrichment_even_with_business_names(self):
        inspection=dict(source_id='peel_health_food',source_key='food-1',
                        description='Restaurant public health inspection',
                        company_name='Sample Restaurant',address='3078 Mayfield Rd',
                        city='Brampton',source_group='MUNICIPAL_CHANGE')
        self.assertEqual(selector.classify(inspection)[0],'ENRICHMENT_ONLY')
        self.assertEqual(policy.research_route(inspection),'ENRICHMENT_ONLY')
        with tempfile.TemporaryDirectory() as t:
            t=Path(t);write_csv(t/'in.csv',[inspection,permit()])
            result=selector.run(t/'in.csv',t/'out')
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['lane'],'PERMIT_REVIEW')
            self.assertEqual(len(selector.read_csv(t/'out'/'CANDIDATES_V4_ENRICHMENT_ONLY.csv')),1)

    def test_old_queue_inspections_archive_and_changed_permits_become_first(self):
        today=dt.date(2026,10,19)
        old={'project_id':'old-food','source_id':'peel_health_food',
             'lane':'SOURCE_UPDATE_WATCH','description':'Restaurant health inspection',
             'address':'3078 Mayfield Road','_queued_on':'2026-09-01'}
        oldpermit={'project_id':'old-permit','source_id':'toronto_active_building_permits',
                   'lane':'SOURCE_UPDATE_WATCH','description':'Commercial tenant fit-out',
                   'address':'25 The West Mall Toronto','_queued_on':'2026-10-01'}
        recent=dict(oldpermit,project_id='new-permit',lane='PERMIT_REVIEW',
                    address='125 Front Street Toronto',_queued_on='2026-10-19')
        enrolled=queue.build([recent],[old,oldpermit],{},today)
        ordered=queue.due(enrolled,{},today)
        self.assertEqual({r['project_id'] for r in ordered},{'new-permit','old-permit'})
        self.assertEqual(ordered[0]['lane'],'PERMIT_REVIEW')
        self.assertNotIn('old-food',[r['project_id'] for r in enrolled])

    def test_missing_address_never_crashes_public_project_verification(self):
        # Municipal sources may have a valid project ID/description but no
        # street address; older code raised IndexError via splitlines()[0].
        for address in ('', None, '\\n'):
            row={'source_id':'brampton_building_permits',
                 'source_keys':'26 155543 BLD|00','address':address,
                 'city':'Brampton',
                 'description':'Interior alteration to commercial building'}
            with self.subTest(address=address):
                self.assertEqual(policy._civic_address(row),'')
                self.assertFalse(policy.project_evidence(
                    row,'Commercial alteration of a different address in Brampton',
                    'https://city.example/projects/elsewhere'))
                self.assertTrue(policy.project_evidence(
                    row,'Official permit 26 155543 BLD was submitted',
                    'https://city.example/projects/permit'))

    def test_matching_operator_only_or_wrong_city_never_verifies_project(self):
        row={'project_id':'peel-304','source_id':'brampton_building_permits',
             'address':'3078 Mayfield Road, Brampton, ON','city':'Brampton',
             'company_name':'Sample Restaurant',
             'source_keys':'26 155543 BLD|00'}
        self.assertFalse(policy.project_evidence(row,
                          'Sample Restaurant recently renovated a different location in Owen Sound',
                          'https://other-company.ca/story'))
        self.assertFalse(policy.project_evidence(row,
                          'Commercial renovation at 3078 Mayfield Road in Owen Sound',
                          'https://other-company.ca/story'))
        self.assertFalse(policy.project_evidence(row,
                          '3078 Mayfield Road Brampton Ontario business directory',
                          'https://www.allbiz.ca/3078-mayfield'))
        self.assertFalse(policy.project_evidence(row,
                          '3078 Mayfield Road Brampton Ontario',
                          'https://somewhere.ca/location'))
        self.assertTrue(policy.project_evidence(row,
                          'Permit application for 3078 Mayfield Road Brampton for commercial renovations',
                          'https://municipal.example/permit'))
        self.assertTrue(policy.project_evidence(row,
                          'Building permit 26 155543 BLD is listed as under review.',
                          'https://municipal.example/permits'))

    def test_company_channel_is_discovered_from_public_business_page(self):
        with tempfile.TemporaryDirectory() as t:
            with closing(ai.v5._ledger(Path(t)/'v5_ai_budget.sqlite')) as db:
                def provider(path,payload):
                    self.assertEqual(path,'/v1/tools/search')
                    return {'results':[
                        {'url':'https://www.yellowpages.ca/example','content':'Sample Industries info@fake.ca'},
                        {'url':'https://sampleindustries.ca/contact',
                         'content':'Sample Industries Ltd. contact our office at info@sampleindustries.ca'}
                    ]}
                contact,n=ai.find_public_business_contact(
                    {'project_id':'P123'},'Sample Industries Ltd.', 'test',db,
                    '2026-10-19',0,provider)
                self.assertEqual(n,1)
                self.assertEqual(contact['contact'],'info@sampleindustries.ca')
                self.assertEqual(contact['contact_provenance'],'PUBLIC_MATCHING_COMPANY_PAGE')
                self.assertEqual(contact['contact_source_url'],'https://sampleindustries.ca/contact')

    def test_report_distinguishes_legacy_hits_from_new_project_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            rows=[dict(project_id='new',address='25 The West Mall',source_id='toronto_active_building_permits',
                       priority='PERMIT_REVIEW',operator='Example Business',buyer_fit='Hypothesis only: HVAC',
                       contact='info@example.ca',contact_source_url='https://example.ca/contact',
                        contact_source_quality='CONTACT_ON_BRANDED_BUSINESS_PAGE',
                       status='AI_EVIDENCE_REVIEW',project_evidence_verified='YES',
                       source_urls='https://toronto.ca/permits/25thewestmall',
                       evidence_tier='OFFICIAL_PAGE_MATCHED'),
                  dict(project_id='legacy',address='100 Dundas',
                       source_id='toronto_active_building_permits',priority='SOURCE_UPDATE_WATCH',
                       status='AI_EVIDENCE_REVIEW',
                       source_urls='https://yellowpages.ca/project-100')]
            write_csv(p/'GTA_RADAR_V8_INVESTIGATIONS.csv',rows)
            write_csv(p/'GTA_RADAR_V8_PENDING_QUEUE.csv',[
                dict(project_id='pending',source_id='toronto_active_building_permits',
                     lane='PERMIT_REVIEW',address='35 Front Street',
                     description='Office renovation')])
            write_csv(p/'GTA_RADAR_V8_COMPANY_ENRICHMENT.csv',[
                dict(project_id='food',source_id='peel_health_food',
                     address='1 Test Ave',description='Restaurant inspection')])
            counts=reports.build(p)
            self.assertEqual(counts['project_opportunities'],1)
            self.assertEqual(counts['public_company_contacts'],1)
            self.assertEqual(counts['backlog'],1)
            self.assertEqual(counts['company_enrichment'],1)
            self.assertEqual(counts['legacy_rechecks'],1)
            self.assertEqual(reports.read(p/'GTA_RADAR_PROJECT_OPPORTUNITIES.csv')[0]['sale_ready'],'NO')
            self.assertIn('Research prospects', (p/'GTA_RADAR_LEAD_INTELLIGENCE.html').read_text())


if __name__=='__main__':
    unittest.main()
