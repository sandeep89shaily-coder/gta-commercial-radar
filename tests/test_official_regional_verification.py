"""Regression cases for municipal exact-ID verification and regional coverage."""
import csv
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import official_record_verifier as official
import regional_candidate_bridge as bridge
import commercial_selector_v4 as v4

DAY=dt.date(2026,10,19)

def setup_db(path, rows):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE records_current (source_id TEXT, record_key TEXT, '
                   'source_date TEXT, normalized_json TEXT, active INTEGER)')
        for sid,key,date,record in rows:
            db.execute("INSERT INTO records_current VALUES(?,?,?,?,1)",
                       (sid,key,date,json.dumps(record)))
        db.commit()


def row(source_id,key,date,company,address,description,status="Under review",region="Peel"):
    return (source_id,key,date,dict(entity_name=company,address=address,
                                    description=description,status=status,
                                    region=region,commercial_relevance="HIGH"))

class ExactGovernmentRecordVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        setup_db(self.root/'radar.sqlite',[
            row("mississauga_issued_building_permits","BP-600",
                "2026-10-15","","600 Dundas Street W",
                "Commercial office renovation",status="Issued"),
            row("brampton_building_permits","BP-700",
                "2026-10-16","Sourced Builder Inc","700 Queen Street W",
                "Industrial warehouse expansion",status="Application"),
            row("york_region_active_development_applications","YR-12",
                "2026-09-29","North Planning Ltd","12 Main Street",
                "New warehouse development",region="York")
        ])

    def test_mississauga_exact_status_and_no_invented_operator(self):
        candidate=dict(source_id="mississauga_issued_building_permits",
                       source_keys="BP-600",address="600 Dundas St W",city="Mississauga")
        urls=[]
        def request(url):
            urls.append(url)
            return dict(features=[dict(attributes={
                'BP_NO': 'BP-600','STATUS':'Issued',
                'ADDRESS':'600 Dundas Street W','DESCRIPTION':'Office renovation',
                'ISSUE_DATE':1792368000000})])
        result=official.verify(candidate,self.root,transport=request)
        self.assertEqual(result['official_verification_level'],'OFFICIAL_ID_AND_STATUS_MATCH')
        self.assertEqual(result['official_status'],'Issued')
        self.assertEqual(result['official_company'],'')
        self.assertEqual(result['official_permit_id'],'BP-600')
        self.assertEqual(result['official_live_attempted'],'YES')
        self.assertEqual(parse_qs(urlparse(urls[0]).query)['where'],["BP_NO = 'BP-600'"])
        self.assertNotIn("Purchasing", result['official_status'])

    def test_brampton_builder_is_not_the_project_operator(self):
        candidate=dict(source_id="brampton_building_permits",source_keys="BP-700",
                       address="700 Queen St W")
        result=official.verify(candidate,self.root,live=False)
        self.assertEqual(result['official_verification_level'],'COLLECTOR_SOURCE_MATCH')
        self.assertEqual(result['official_company'],'Sourced Builder Inc')
        self.assertEqual(result['official_company_role'],'builder')
        self.assertIn('local collector',result['official_status_basis'])

    def test_wrong_id_or_wrong_address_cannot_corrobate(self):
        candidate=dict(source_id="mississauga_issued_building_permits",
                       source_keys="BP-600",address="600 Dundas Street W")
        def different(url):
            return {'features':[{'attributes':{
                'BP_NO':'BP-601','ADDRESS':'600 Dundas Street W','STATUS':'Issued'}}]}
        result=official.verify(candidate,self.root,transport=different)
        self.assertEqual(result['official_verification_level'],'COLLECTOR_SOURCE_MATCH')
        self.assertNotEqual(result['official_verification_level'],'OFFICIAL_ID_AND_STATUS_MATCH')
        def mismatch(url):
            return {'features':[{'attributes':{
                'BP_NO':'BP-600','ADDRESS':'700 Dundas Street W','STATUS':'Issued'}}]}
        result=official.verify(candidate,self.root,transport=mismatch)
        self.assertEqual(result['official_verification_level'],'COLLECTOR_SOURCE_MATCH')
        self.assertIn('disagree',result['official_verification_note'])

    def test_grouped_ids_and_untrusted_sources_do_not_trigger_arbitrary_queries(self):
        result=official.verify(dict(source_id='mississauga_issued_building_permits',
                   source_keys='BP-600 | BP-601'),self.root,
                   transport=lambda u:self.fail('should not call any query'))
        self.assertEqual(result['official_verification_level'],'NOT_VERIFIED')
        self.assertEqual(official.published_query(
            {'id':'unconfigured','collector':'arcgis','query_url':'https://evil.tld/query'},'BP-600'),'')

    def test_regional_bridge_preserves_timestamp_basis_and_non_toronto_spread(self):
        input_file=self.root/'opportunities_ALL_REVIEW_ONLY.csv'
        with input_file.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['source_id','source_key','description','address','city',
                                           'event_date','event_date_basis','source_group'])
            w.writeheader()
            w.writerow(dict(source_id='toronto_active_building_permits',
                            source_key='26 123456 BLD|00',description='New office renovation',
                            address='40 Front St W',city='Toronto',event_date='2026-10-19',
                            event_date_basis='CHANGE_DETECTED',source_group='MUNICIPAL'))
        combined,summary=bridge.selection_input(input_file,self.root/'radar.sqlite',
                                                 self.root,today=DAY)
        self.assertGreaterEqual(summary['regional_source_records_added'],3)
        with combined.open(encoding='utf-8-sig',newline='') as file:
            rows=list(csv.DictReader(file))
        self.assertEqual({r['source_id'] for r in rows},
                         {'toronto_active_building_permits',
                          'mississauga_issued_building_permits',
                          'brampton_building_permits',
                          'york_region_active_development_applications'})
        for r in rows:
            if r['source_group']=='REGIONAL_ARCHIVED_SOURCE':
                self.assertEqual(r['event_date_basis'],
                                 'EXISTING_PUBLISHED_SOURCE_DATE_NOT_NEW_EVENT')
        selected=v4.run(combined,self.root/'selection',self.root/'radar.sqlite')
        self.assertTrue({'Brampton','Mississauga','York Region'} &
                        {r.get('city') for r in selected})
        coverage=bridge.STATS
        self.assertTrue((self.root/'GTA_RADAR_REGIONAL_COVERAGE.csv').is_file())

    def test_no_database_is_reported_as_no_source_records(self):
        entries,inventory=bridge.bridge(self.root/'missing.sqlite',self.root,today=DAY)
        self.assertFalse(entries)
        self.assertTrue(any(r['reason']=='NO_ACTIVE_SOURCE_RECORDS_IN_LOCAL_DATABASE'
                            for r in inventory))
        self.assertTrue(any(r['reason'].startswith('STAGED_DISABLED')
                            for r in inventory))


if __name__=='__main__':
    unittest.main()
