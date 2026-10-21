"""Commercial regional intake, live record IDs and contact provenance regression.

All tests run with fabricated SQLite rows and provider responses. They must not
be interpreted as proof that a disabled live source is reachable/licensed.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import regional_candidate_bridge as bridge
import official_record_verifier as official
import commercial_selector_v4 as selector
import company_contact_policy as company
import commercial_lead_reports as reports
import v8_ai_queue as queue
import v8_deepseek_native as native

TODAY=dt.date(2026,10,20)

def save(path,rows,cols=None):
    cols=cols or list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore')
        w.writeheader();w.writerows(rows)

class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)
        with closing(sqlite3.connect(self.p/'radar.sqlite')) as db:
            db.execute('CREATE TABLE records_current (source_id TEXT, record_key TEXT, '
                       'source_date TEXT, normalized_json TEXT, active INTEGER)')
            db.commit()

    def insert(self,sid,key,date,description,address,company='',status='Applied'):
        record=dict(source_id=sid,description=description,address=address,
                    entity_name=company,status=status,commercial_relevance='HIGH')
        with closing(sqlite3.connect(self.p/'radar.sqlite')) as db:
            db.execute('INSERT INTO records_current VALUES(?,?,?,?,1)',
                       (sid,key,date,json.dumps(record)))
            db.commit()

    def test_region_quota_applies_after_noncommercial_screening(self):
        sid='waterloo_city_building_permits'
        for n in range(28):
            self.insert(sid,'P'+str(n)+'|2026', '2026-10-20',
                        'New single family detached dwelling',
                        f'{100+n} Home Street')
        self.insert(sid,'WX-11|261','2026-10-18',
                    'Industrial warehouse expansion and construction',
                    '100 Industry Boulevard')
        self.insert(sid,'WX-12|262','2026-10-17',
                    'Restaurant tenant fit-out and installation',
                    '200 Market Road')
        candidates,coverage=bridge.bridge(self.p/'radar.sqlite',self.p,today=TODAY,
                                         per_source=2,per_region=2)
        water=[r for r in candidates if r['source_id']==sid]
        self.assertEqual(len(water),2)
        self.assertTrue(all('dwelling' not in r['description'] for r in water))
        info=next(r for r in coverage if r['source_id']==sid)
        self.assertEqual(info['eligible_source_dated_records'],30)
        self.assertEqual(info['commercial_qualified_records'],2)
        self.assertEqual(info['rejected_noncommercial_records'],28)
        self.assertEqual(info['selected_for_research'],2)

    def test_queue_interleaves_proven_regions_without_dropping_toronto(self):
        rows=[{'project_id':f'T{i}','source_id':'toronto_active_building_permits'}
              for i in range(20)]
        rows.extend([{'project_id':'P1','source_id':'brampton_building_permits'},
                     {'project_id':'P2','source_id':'mississauga_issued_building_permits'},
                     {'project_id':'N1','source_id':'st_catharines_building_permits'},
                     {'project_id':'W1','source_id':'waterloo_city_building_permits'}])
        ranked=queue.fair_regional_order(rows)
        self.assertEqual(len(ranked),len(rows))
        self.assertEqual({r['project_id'] for r in ranked},{r['project_id'] for r in rows})
        self.assertEqual([r['project_id'] for r in ranked[:4]],['P1','W1','N1','T0'])
        self.assertEqual([r['project_id'] for r in ranked[4:6]],['P2','T1'])

    def test_composite_waterloo_id_live_match_and_official_link(self):
        sid='waterloo_city_building_permits'
        self.insert(sid,'WP-90|2026','2026-10-19',
                    'Industrial warehouse alteration','100 King Street')
        candidate=dict(source_id=sid,source_keys='WP-90|2026',
                       address='100 King St',city='Waterloo')
        seen=[]
        def request(url):
            seen.append(url)
            return {'features':[{'attributes':{
                'PERMIT_ID':'WP-90','PERMIT_NUM':'2026','STATUS':'Under Review',
                'ADDRESS':'100 King Street','DESCRIPTN':'Warehouse renovation'}}]}
        found=official.verify(candidate,self.p,transport=request)
        self.assertEqual(found['official_verification_level'],'OFFICIAL_ID_AND_STATUS_MATCH')
        self.assertEqual(found['official_permit_id'],'WP-90|2026')
        clause=parse_qs(urlparse(seen[0]).query)['where'][0]
        self.assertIn('PERMIT_ID',clause)
        self.assertIn('PERMIT_NUM',clause)
        self.assertIn('2026',clause)

    def test_niagara_exact_composite_id_no_false_merge(self):
        sid='st_catharines_building_permits'
        self.insert(sid,'2026|0045','2026-10-19',
                    'Industrial construction','40 Warehouse Street')
        row=dict(source_id=sid,source_keys='2026|0045',
                 address='40 Warehouse Street',city='St. Catharines')
        def provider(url):
            return {'features':[{'attributes':{'FOLDERYEAR':2026,
                       'FOLDERSEQUENCE':45,'STATUSDESC':'Issued',
                       'PROPSTREET':'40 Warehouse Street'}}]}
        # Leading zeros are identity-bearing; don't quietly match 0045 to 45.
        found=official.verify(row,self.p,transport=provider)
        self.assertNotEqual(found['official_verification_level'],'OFFICIAL_ID_AND_STATUS_MATCH')

    def test_selector_exposes_exact_official_lookup_not_just_address(self):
        sid='brampton_building_permits'
        self.insert(sid,'BR-888','2026-10-19','Industrial warehouse expansion',
                    '25 Queen Street West','Example Builder')
        src=self.p/'incoming.csv'
        save(src,[dict(source_id=sid,source_key='BR-888',
                        description='Industrial warehouse expansion',
                        address='25 Queen Street West',city='Brampton',
                        source_group='REGIONAL_ARCHIVED_SOURCE')])
        v=selector.run(src,self.p/'selection',self.p/'radar.sqlite')
        self.assertEqual(len(v),1)
        self.assertEqual(v[0]['record_source_url_basis'],'EXACT_ID_OFFICIAL_LOOKUP_UNCHECKED')
        self.assertIn('PERMITNUMBER',v[0]['record_source_url'])

    def test_contacts_must_come_from_a_matching_business_page(self):
        self.assertFalse(company.company_owned_page(
            'Canada Life Assurance Company',
            'https://www.gov.nu.ca/documents/Canada-Life-Managers-2004.pdf'))
        self.assertFalse(company.company_owned_page(
            'CIBC','https://ontarioconstructionnews.com/articles/cibc'))
        self.assertTrue(company.company_owned_page(
            'Sample Industries Ltd','https://sampleindustries.ca/contact'))
        self.assertTrue(company.matching_business_channel(
            'Sample Industries Ltd','https://sampleindustries.ca/contact',
            'Sample Industries Ltd. info@sampleindustries.ca', 'info@sampleindustries.ca'))
        self.assertFalse(company.matching_business_channel(
            'Sample Industries Ltd','https://sampleindustries.ca/contact',
            'Sample Industries Ltd. fake@gmail.com','fake@gmail.com'))

    def test_legacy_bad_contacts_remain_visible_not_promoted(self):
        rows=[dict(project_id='P1',source_id='toronto_active_building_permits',
                   lane='PERMIT_REVIEW',description='Commercial office fit-out',
                   address='55 King St',operator='Canada Life Assurance Company',
                   contact='866-292-7825',
                   contact_source_url='https://www.gov.nu.ca/documents/Canada-Life-Managers-2004.pdf',
                   status='AI_EVIDENCE_REVIEW',project_evidence_verified='YES',
                   source_urls='https://toronto.ca/permit/p1',
                   evidence_tier='OFFICIAL_PAGE_MATCHED'),
              dict(project_id='P2',source_id='toronto_active_building_permits',
                   lane='PERMIT_REVIEW',description='Industrial warehouse expansion',
                   address='125 Queen St',operator='Sample Industries Ltd.',
                   contact='info@sampleindustries.ca',
                   contact_source_url='https://sampleindustries.ca/contact',
                   contact_source_quality='CONTACT_ON_BRANDED_BUSINESS_PAGE',
                   status='AI_EVIDENCE_REVIEW',project_evidence_verified='YES',
                   source_urls='https://toronto.ca/permit/p2')]
        save(self.p/'GTA_RADAR_V8_INVESTIGATIONS.csv',rows)
        summary=reports.build(self.p)
        self.assertEqual(summary['project_opportunities'],2)
        self.assertEqual(summary['public_company_contacts'],1)
        self.assertEqual(summary['contact_sources_requiring_recheck'],1)
        outputs={r['project_id']:r for r in reports.read(
            self.p/'GTA_RADAR_PROJECT_OPPORTUNITIES.csv')}
        self.assertEqual(outputs['P1']['contact'],'')
        self.assertEqual(outputs['P1']['unverified_contact'],'866-292-7825')
        self.assertEqual(outputs['P2']['contact'],'info@sampleindustries.ca')
        self.assertTrue((self.p/'GTA_RADAR_VERIFIED_REGIONAL_OUTCOMES.csv').exists())

if __name__=='__main__':
    unittest.main()
