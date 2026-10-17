"""Regression tests for evidence-first V4 against historic selector failures."""
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import commercial_selector_v4 as v4

def row(desc,key='26 233562 BLD|00',group='MUNICIPAL_CHANGE'):
    return {'description':desc,'source_id':'toronto_active_building_permits',
            'source_key':key,'source_group':group,'address':'650 DUNDAS ST E',
            'city':'Toronto','company_name':'',
            'event_date':'2026-10-16T10:02:18+00:00',
            'event_date_basis':'CHANGE_DETECTED_NOT_PERMIT_ISSUED'}

class V4RegressionTests(unittest.TestCase):
    def test_residential_and_no_work(self):
        self.assertEqual(v4.classify(row('New 2-storey garden suite'))[0],'EXCLUDE_SMALL_RESIDENTIAL')
        self.assertEqual(v4.classify(row('20-storey mixed-use residential tower, 183 dwelling units and retail'))[0],'EXCLUDE_RESIDENTIAL_LED')
        self.assertEqual(v4.classify(row('As-built documentation of restaurant. No new construction is proposed'))[0],'EXCLUDE_NO_WORK')
        self.assertEqual(v4.classify(row('New industrial warehouse construction'))[0],'SOURCE_UPDATE_WATCH')

    def test_change_date_is_not_permit_issuance(self):
        r=row('Restaurant tenant fit-out and plumbing')
        x=v4.summarize([r],{})
        self.assertEqual(x['lane'],'SOURCE_UPDATE_WATCH')
        self.assertLessEqual(x['review_priority'],20)
        self.assertIn('NOT ISSUANCE',x['date_basis'])
        copy=dict(r,source_group='MUNICIPAL',event_date_basis='SOURCE_DATE')
        self.assertEqual(v4.classify(copy)[0],'PERMIT_REVIEW')

    def test_group_trades_without_changing_input(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            records=[row('Restaurant tenant fit-out HVAC plumbing',key=f'26 233562 {t}|00') for t in ('BLD','HVA','PLB')]
            records.append(row('Residential apartment building 183 dwelling units',key='26 123456 BLD|00'))
            src=td/'input.csv'
            with src.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
            before=src.read_bytes()
            result=v4.run(src,td/'out')
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['permit_count'],3)
            self.assertEqual(result[0]['permit_types'],'BLD, HVA, PLB')
            self.assertEqual(src.read_bytes(),before)
            self.assertTrue((td/'out'/'CANDIDATES_V4_EXCLUDED_AUDIT.csv').is_file())
            self.assertTrue((td/'out'/'commercial_candidates_v4.html').is_file())

    def test_read_only_status_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'radar.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE records_current(source_id TEXT,record_key TEXT,active INTEGER,source_date TEXT,normalized_json TEXT)')
                db.execute('INSERT INTO records_current VALUES(?,?,?,?,?)',
                    ('toronto_active_building_permits','26 233562 BLD|00',1,'2026-10-11',
                     json.dumps({'status':'Under Review','evidence_url':'https://example.com/permit/1'})))
            info=v4.load_metadata(path,[row('Industrial warehouse expansion')])
            result=v4.summarize([row('Industrial warehouse expansion')],info)
            self.assertEqual(result['current_source_status'],'Under Review')
            self.assertEqual(result['source_record_date'],'2026-10-11')
            self.assertEqual(result['record_source_url'],'https://example.com/permit/1')

    def test_125_candidates_no_quota(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            records=[row('New industrial factory construction',f'26 {i:06d} BLD|00','MUNICIPAL') for i in range(125)]
            inp=td/'input.csv'
            with inp.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
            output=v4.run(inp,td/'out')
            self.assertEqual(len(output),125)
            self.assertTrue(all(x['review_status'].startswith('RESEARCH ONLY') for x in output))

if __name__=='__main__':
    unittest.main()
