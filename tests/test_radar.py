import json, sqlite3, tempfile, unittest, io
from pathlib import Path
import pandas as pd
from radar import (normalize_row, stable_key, normalized_summary, open_db, process_snapshot, Snapshot,
                   resolve_ckan_package, choose_ckan_resource, parse_tabular_bytes, clear_source_current,
                   set_source_state, _ckan_unchanged, _arcgis_date_clause,
                   _agco_resolve_download, _agco_row_is_gta, _parse_ero_search_cards, _ero_business_relevant)

class RadarTests(unittest.TestCase):
    def test_stable_key_composite(self):
        s={'key_fields':['PERMIT_NUM','REVISION_NUM']}
        r=normalize_row({'Permit Num':'123','Revision Num':'2'})
        self.assertEqual(stable_key(r,s),'123|2')

    def test_miss_residential_not_commercial(self):
        s={'id':'mississauga_issued_building_permits','name':'x','family':'permit','jurisdiction':'Mississauga','region':'Peel','entity_fields':[],'address_fields':['ADDRESS'],'description_fields':['DESCRIPTION'],'status_fields':['STATUS'],'date_fields':['ISSUE_DATE'],'value_fields':[]}
        r=normalize_row({'FILE_TYPE':'RESIDENTIAL','ADDRESS':'1 TEST ST','DESCRIPTION':'NEW HOUSE'})
        self.assertEqual(normalized_summary(r,s)['commercial_relevance'],'LOW')

    def test_miss_commercial_high(self):
        s={'id':'mississauga_issued_building_permits','name':'x','family':'permit','jurisdiction':'Mississauga','region':'Peel','entity_fields':[],'address_fields':['ADDRESS'],'description_fields':['DESCRIPTION'],'status_fields':['STATUS'],'date_fields':['ISSUE_DATE'],'value_fields':['EST_CON_VALUE']}
        r=normalize_row({'FILE_TYPE':'COMMERCIAL','ADDRESS':'2 TEST ST','DESCRIPTION':'TENANT FIT UP','EST_CON_VALUE':250000})
        self.assertEqual(normalized_summary(r,s)['commercial_relevance'],'HIGH')

    def test_first_run_is_baseline_then_update_is_change(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            con=open_db(td/'x.sqlite')
            try:
                s={'id':'demo','name':'Demo','family':'business_licence','jurisdiction':'Toronto','region':'Toronto','key_fields':['ID'],'date_fields':['DATE'],'entity_fields':['NAME'],'address_fields':['ADDRESS'],'description_fields':['TYPE'],'status_fields':['STATUS'],'value_fields':[],'complete_snapshot':True}
                a=[normalize_row({'ID':'1','NAME':'A','ADDRESS':'X','STATUS':'ACTIVE'})]
                r1=process_snapshot(con,Snapshot(s,a,b'',"x",{}),td/'raw')
                self.assertTrue(r1['baseline'])
                self.assertEqual(con.execute('select count(*) from changes').fetchone()[0],0)
                b=[normalize_row({'ID':'1','NAME':'A','ADDRESS':'X','STATUS':'CLOSED'}),normalize_row({'ID':'2','NAME':'B','ADDRESS':'Y','STATUS':'ACTIVE'})]
                r2=process_snapshot(con,Snapshot(s,b,b'',"x",{}),td/'raw')
                self.assertFalse(r2['baseline'])
                kinds=[x[0] for x in con.execute('select change_type from changes order by change_id')]
                self.assertEqual(kinds,['UPDATED','NEW'])
            finally:
                con.close()

    def test_removed_only_after_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            con=open_db(td/'x.sqlite')
            try:
                s={'id':'demo','name':'Demo','family':'regulated_registry','jurisdiction':'Ontario','region':'Ontario','key_fields':['ID'],'date_fields':[],'entity_fields':['NAME'],'address_fields':[],'description_fields':[],'status_fields':[],'value_fields':[],'complete_snapshot':True}
                process_snapshot(con,Snapshot(s,[{'ID':'1','NAME':'A'},{'ID':'2','NAME':'B'}],b'',"x",{}),td/'raw')
                r=process_snapshot(con,Snapshot(s,[{'ID':'2','NAME':'B'}],b'',"x",{}),td/'raw')
                self.assertEqual(r['removed'],1)
                self.assertEqual(con.execute("select count(*) from changes where change_type='REMOVED'").fetchone()[0],1)
            finally:
                con.close()

    def test_exact_ckan_package_uses_package_show_not_search(self):
        class Resp:
            def __init__(self, data): self._data=data
            def json(self): return self._data
        class FakeHttp:
            def __init__(self): self.calls=[]
            def get(self, url, **kwargs):
                self.calls.append((url, kwargs.get('params')))
                self_outer = self
                return Resp({'success': True, 'result': {'id':'pkg-1','title':'Dinesafe','resources':[]}})
        h=FakeHttp()
        src={'api_base':'https://example/api/3/action','package_id':'pkg-1','expected_package_title':'Dinesafe'}
        pkg=resolve_ckan_package(src,h)
        self.assertEqual(pkg['id'],'pkg-1')
        self.assertEqual(len(h.calls),1)
        self.assertTrue(h.calls[0][0].endswith('/package_show'))

    def test_pinned_ckan_resource_cannot_fall_through(self):
        pkg={'title':'Dinesafe','resources':[{'id':'right','name':'Dinesafe.csv','format':'CSV'}, {'id':'wrong','name':'SwimSafe.csv','format':'CSV'}]}
        src={'resource_id':'right','preferred_resource_names':['Dinesafe'],'preferred_formats':['CSV']}
        self.assertEqual(choose_ckan_resource(pkg,src)['id'],'right')
        src['resource_id']='missing'
        with self.assertRaises(RuntimeError):
            choose_ckan_resource(pkg,src)


    def test_xlsx_bytes_parse_explicit_engine(self):
        bio=io.BytesIO()
        pd.DataFrame([{"LICENCE_NUMBER":"123","CITY":"Toronto"}]).to_excel(bio,index=False,engine="openpyxl")
        rows=parse_tabular_bytes(bio.getvalue(),"https://example.test/file.xlsx","XLSX")
        self.assertEqual(rows[0]["LICENCE_NUMBER"],"123")

    def test_childcare_resource_prefers_real_xlsx_download(self):
        pkg={"title":"Licensed child care facilities in Ontario","resources":[
            {"id":"support","name":"Data dictionary English and French","format":"XLSX","url":"https://example.test/dataset/page"},
            {"id":"data","name":"August 2026","format":"XLSX","url":"https://example.test/child_care_aug_2026.xlsx","last_modified":"2026-08-31"}
        ]}
        src={"preferred_resource_names":["Licensed child care facilities","English"],"preferred_formats":["XLSX"],"resource_url_must_end_with":[".xlsx"]}
        self.assertEqual(choose_ckan_resource(pkg,src)["id"],"data")


    def test_private_school_pinned_english_domestic_resource(self):
        pkg={"title":"Private school contact information","resources":[
            {"id":"intl","name":"International Private Schools","format":"CSV","url":"https://example/international_private_schools_eng.csv"},
            {"id":"d16de265-35e9-4277-9381-0c311e802e39","name":"Private school contact information","format":"CSV","url":"https://example/private_school_contact_information_eng.csv"},
        ]}
        src={
            "resource_id":"d16de265-35e9-4277-9381-0c311e802e39",
            "expected_resource_name":"Private school contact information",
            "resource_url_contains":["private_school_contact_information_eng.csv"],
            "resource_url_excludes":["international_private_schools"],
        }
        self.assertEqual(choose_ckan_resource(pkg,src)["id"],"d16de265-35e9-4277-9381-0c311e802e39")

    def test_pinned_resource_identity_guard_rejects_wrong_url(self):
        pkg={"title":"Private school contact information","resources":[
            {"id":"d16de265-35e9-4277-9381-0c311e802e39","name":"Private school contact information","format":"CSV","url":"https://example/international_private_schools_eng.csv"}
        ]}
        src={
            "resource_id":"d16de265-35e9-4277-9381-0c311e802e39",
            "expected_resource_name":"Private school contact information",
            "resource_url_contains":["private_school_contact_information_eng.csv"],
            "resource_url_excludes":["international_private_schools"],
        }
        with self.assertRaises(RuntimeError):
            choose_ckan_resource(pkg,src)

    def test_source_universe_change_refuses_false_diff_until_rebaseline(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            con=open_db(td/'x.sqlite')
            try:
                s={'id':'demo','name':'Demo','family':'business_licence','jurisdiction':'Toronto','region':'Toronto',
                   'collector':'arcgis','query_url':'https://example/query','server_where':'1=1',
                   'key_fields':['ID'],'date_fields':[],'entity_fields':['NAME'],'address_fields':[],
                   'description_fields':[],'status_fields':[],'value_fields':[],'complete_snapshot':True}
                process_snapshot(con,Snapshot(s,[{'ID':'1','NAME':'A'}],b'',"x",{}),td/'raw')
                s2=dict(s); s2['server_where']="TYPE='COMMERCIAL'"
                with self.assertRaisesRegex(RuntimeError, "rebaseline"):
                    process_snapshot(con,Snapshot(s2,[{'ID':'1','NAME':'A'}],b'',"x",{}),td/'raw')
                n=clear_source_current(con,'demo')
                self.assertEqual(n,1)
                r=process_snapshot(con,Snapshot(s2,[{'ID':'1','NAME':'A'}],b'',"x",{}),td/'raw')
                self.assertTrue(r['baseline'])
                self.assertEqual(con.execute("select count(*) from changes").fetchone()[0],0)
            finally:
                con.close()



    def test_partial_snapshot_never_removes_missing_rows(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); con=open_db(td/'x.sqlite')
            try:
                s={'id':'demo2','name':'Demo','family':'business_licence','jurisdiction':'Toronto','region':'Toronto',
                   'collector':'ckan','key_fields':['ID'],'date_fields':[],'entity_fields':['NAME'],'address_fields':[],
                   'description_fields':[],'status_fields':[],'value_fields':[],'complete_snapshot':True}
                process_snapshot(con,Snapshot(s,[{'ID':'1','NAME':'A'},{'ID':'2','NAME':'B'}],b'','x',{},True,'full'),td/'raw')
                r=process_snapshot(con,Snapshot(s,[{'ID':'1','NAME':'A2'}],b'','x',{'snapshot_mode':'incremental_datastore'},False,'incremental_datastore'),td/'raw')
                self.assertEqual(r['removed'],0)
                self.assertEqual(r['current'],2)
            finally: con.close()

    def test_material_change_uses_summary_not_raw_internal_id(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); con=open_db(td/'x.sqlite')
            try:
                s={'id':'demo3','name':'Demo','family':'business_licence','jurisdiction':'Toronto','region':'Toronto',
                   'collector':'ckan','key_fields':['ID'],'date_fields':[],'entity_fields':['NAME'],'address_fields':[],
                   'description_fields':[],'status_fields':[],'value_fields':[],'complete_snapshot':True}
                process_snapshot(con,Snapshot(s,[{'ID':'1','NAME':'A'}],b'','x',{},True,'full'),td/'raw')
                r=process_snapshot(con,Snapshot(s,[{'ID':'1','NAME':'A','_id':999}],b'','x',{'snapshot_mode':'incremental_datastore'},False,'incremental_datastore'),td/'raw')
                self.assertEqual(r['updated'],0)
            finally: con.close()

    def test_ckan_metadata_unchanged(self):
        prev={'resource_id':'r1','resource_modified':'2026-10-08T10:00:00'}
        cur={'resource_id':'r1','resource_modified':'2026-10-08T10:00:00','resource_fingerprint':'x'}
        self.assertTrue(_ckan_unchanged(prev,cur))
        cur['resource_modified']='2026-10-08T11:00:00'
        self.assertFalse(_ckan_unchanged(prev,cur))

    def test_arcgis_incremental_clause(self):
        q=_arcgis_date_clause(['PROCESSDATE','INDATE'],'2026-10-05')
        self.assertIn("PROCESSDATE >= DATE '2026-10-05'",q)
        self.assertIn("INDATE >= DATE '2026-10-05'",q)


    def test_agco_download_csv_link_and_last_updated(self):
        html="<html><body><p>Last updated October 8, 2026 8:00 am</p><a href='/export/stores.csv'>Download CSV</a></body></html>"
        url,updated=_agco_resolve_download('https://www.agco.ca/page',html)
        self.assertEqual(url,'https://www.agco.ca/export/stores.csv')
        self.assertEqual(updated,'2026-10-08')

    def test_agco_gta_legacy_toronto_places(self):
        self.assertTrue(_agco_row_is_gta({'MUNICIPALITY_OR_FIRST_NATION':'SCARBOROUGH','STORE_NAME':'X'}))
        self.assertTrue(_agco_row_is_gta({'MUNICIPALITY_OR_FIRST_NATION':'WOODBRIDGE','STORE_NAME':'Y'}))
        self.assertFalse(_agco_row_is_gta({'MUNICIPALITY_OR_FIRST_NATION':'LONDON','STORE_NAME':'Z'}))

    def test_ero_card_parser(self):
        html="<html><body><article><h3><a href='/notice/026-0979'>St. Marys Cement Inc. - Environmental Compliance Approval (air)</a></h3><div>Instrument type: Environmental Compliance Approval (air) Notice type Instrument Notice stage Proposal Proposal posted September 25, 2026 Last updated September 25, 2026 This proposal is for a facility in Burlington, Ontario.</div></article></body></html>"
        rows=_parse_ero_search_cards(html)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['ERO_NUMBER'],'026-0979')
        self.assertEqual(rows[0]['ENTITY_NAME'],'St. Marys Cement Inc.')
        self.assertIn('Environmental Compliance Approval',rows[0]['INSTRUMENT_TYPE'])

    def test_ero_gta_business_filter(self):
        src={'gta_only':True,'include_keywords':['ENVIRONMENTAL COMPLIANCE APPROVAL']}
        self.assertTrue(_ero_business_relevant({'TITLE':'ABC - Environmental Compliance Approval (air)','SUMMARY':'facility in Mississauga Ontario'},src))
        self.assertFalse(_ero_business_relevant({'TITLE':'ABC - Environmental Compliance Approval (air)','SUMMARY':'facility in Ottawa Ontario'},src))
        self.assertFalse(_ero_business_relevant({'TITLE':'Policy consultation','SUMMARY':'Toronto Ontario'},src))

    def test_planning_family_is_not_overclaimed_high(self):
        src={'id':'toronto_development_applications','name':'AIC','jurisdiction':'Toronto','region':'Toronto','family':'planning_application','entity_fields':[],'address_fields':['FULL_ADDRESS'],'description_fields':['APPLICATION_TYPE'],'status_fields':['STATUS_DESC'],'date_fields':['LAST_MODIFIED_DATE'],'value_fields':[]}
        s=normalized_summary({'APPLICATION_NUMBER':'A1','FULL_ADDRESS':'1 KING ST','APPLICATION_TYPE':'Site Plan','STATUS_DESC':'Under Review','LAST_MODIFIED_DATE':'2026-10-08'},src)
        self.assertEqual(s['event_type'],'PLANNING_APPLICATION_RECORD')
        self.assertEqual(s['commercial_relevance'],'UNKNOWN')

if __name__=='__main__': unittest.main()
