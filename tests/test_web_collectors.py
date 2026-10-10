import json
import tempfile
import unittest
from pathlib import Path

from radar import Snapshot, collect_source, open_db, process_snapshot, register_sources, source_status, source_universe_hash
from web_collectors import _canonicalize, _peel_page, collect_peel_health, collect_web_table, discover_csv_url

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((ROOT / "config/sources.json").read_text())
AGCO = next(s for s in SOURCES if s['id'].startswith('agco_'))
PEEL = {**next(s for s in SOURCES if s['id'] == 'peel_health_food'), 'request_pause_seconds': 0, 'baseline_workers': 1}


class Response:
    def __init__(self, text='', headers=None):
        self.text = text
        self.content = text.encode('utf-8')
        self.headers = headers or {}


def table(rows, current=1, total=1, result=True, sort=True):
    headings = ['Facility Name', 'Site Address', 'Facility Type', 'Last Inspection Date']
    if result:
        headings.append('Inspection Result')
    body = '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headings) + '<noscript><th>Details</th></noscript></tr>'
    for key, date in rows:
        body += f'<tr><td>Store {key}</td><td>1 Main St Mississauga</td><td>Restaurant</td><td>{date}</td>'
        if result:
            body += '<td><img alt="Pass"></td>'
        body += f'<noscript><td><a href="/Portal/Facility/Details/{key}">Details</a></td></noscript></tr>'
    body += '</table><table class="pagingtable"><tr><td><span class="selectedpage">' + str(current) + '</span>'
    if total > current:
        body += f'<a href="/Portal/Food/Table?pageNumber={total}">{total}</a>'
    elif current > 1:
        body += f'<a href="/Portal/Food/Table?pageNumber={current-1}">{current-1}</a>'
    body += '</td></tr></table>'
    if sort:
        body += '<select name="SortBy"><option value="MostRecentlyInspected" selected>Recent</option></select>'
    return body


class PeelHttp:
    def __init__(self, pages):
        self.pages, self.calls, self.posts = pages, [], []
    def get(self, url, **kw):
        self.calls.append((url, kw))
        if url == PEEL['url']:
            return Response('<form action="/Portal/" method="post"><input name="AcceptDisclaimerButton" value="Accept"></form>')
        return Response(self.pages[kw['params']['pageNumber']])
    def post(self, url, **kw):
        self.posts.append((url, kw))
        return Response('Accepted')


CSV = 'LicenceNumber,FileNumber,PremisesName,StreetAddress,City,ApplicationStatusEn,PublicNoticeStartDate,AddressID\n,100,Store,2 Main St,TORONTO,In Progress,2026-10-01,A\n'


class CsvHttp:
    def __init__(self, modified='Thu, 08 Oct 2026 11:25:17 GMT', csv=CSV):
        self.calls, self.csv = [], csv
        self.headers = {'ETag': 'v'+modified, 'Last-Modified': modified, 'Content-Length': str(len(csv))}
    def get(self, url, **kw):
        self.calls.append(url)
        if url == AGCO['url']:
            return Response('<script>const csvUrl = "https://www.agco.ca/test.csv";</script>')
        return Response(self.csv, self.headers)
    def head(self, url, **kw):
        return Response(headers=self.headers)


class WebCollectorTests(unittest.TestCase):
    def test_javascript_widget_literal_resolved_without_execution(self):
        self.assertEqual(discover_csv_url('https://example.test/x', '<script>const csvUrl = "/data.csv";</script>'), 'https://example.test/data.csv')
        self.assertEqual(discover_csv_url('https://example.test/x', '<button>Download CSV</button>'), '')

    def test_second_agco_poll_skips_csv_body(self):
        h = CsvHttp()
        first = collect_web_table(AGCO, h, False, force_full=True)
        second = collect_web_table(AGCO, h, False, smart=True, previous_metadata=first.metadata)
        self.assertEqual(second.mode, 'metadata_unchanged')
        self.assertFalse(second.is_complete)
        self.assertEqual(h.calls.count('https://www.agco.ca/test.csv'), 1)

    def test_same_day_resource_change_is_not_skipped(self):
        first = collect_web_table(AGCO, CsvHttp(), False, force_full=True)
        h = CsvHttp(modified='Thu, 08 Oct 2026 12:25:17 GMT')
        second = collect_web_table(AGCO, h, False, smart=True, previous_metadata=first.metadata)
        self.assertEqual(second.mode, 'full')
        self.assertIn('https://www.agco.ca/test.csv', h.calls)
        self.assertEqual(first.rows, second.rows)

    def test_file_key_survives_licence_issuance(self):
        first = collect_web_table(AGCO, CsvHttp(), False)
        second = collect_web_table(AGCO, CsvHttp(csv=CSV.replace(',100,', 'CRSA1,100,')), False)
        self.assertEqual(first.rows[0]['APPLICATION_ID'], second.rows[0]['APPLICATION_ID'])

    def test_exact_municipality_filter(self):
        csv = CSV + 'CRSA2,101,King Store,2 King St,KINGSTON,Cancelled,,B\n'
        rows = collect_web_table(AGCO, CsvHttp(csv=csv), False).rows
        self.assertEqual(len(rows), 1)

    def test_bad_export_never_becomes_empty_complete_snapshot(self):
        with self.assertRaises(RuntimeError):
            collect_web_table(AGCO, CsvHttp(csv='unexpected\nvalue\n'), False)

    def test_server_rendered_html_fallback_follows_next_page(self):
        def page(licence, more=False):
            html='<table><tr>'+''.join('<th>'+x+'</th>' for x in AGCO['table_columns'])+'</tr>'
            html+='<tr><td>'+licence+'</td><td>TORONTO</td><td>Test Store</td><td>2 Main St</td><td>In Progress</td></tr></table>'
            return html+('<a rel="next" href="?page=1">Next</a>' if more else '')
        class HtmlHttp:
            def get(self,url,**kwargs): return Response(page('CRSA2') if '?page=1' in url else page('CRSA1',True))
        snap=collect_web_table(AGCO,HtmlHttp(),False)
        self.assertTrue(snap.is_complete)
        self.assertEqual(len(snap.rows),2)
        self.assertEqual(snap.metadata['delivery'],'html_table')

    def test_duplicate_application_id_refused(self):
        with self.assertRaises(RuntimeError):
            collect_web_table(AGCO, CsvHttp(csv=CSV + CSV.splitlines()[1]+'\n'), False)

    def test_peel_noscript_details_and_image_status(self):
        rows, pages, _ = _peel_page(table([('abc','2026-10-08')]), PEEL['table_url'])
        self.assertEqual(rows[0]['FACILITY_ID'], 'abc')
        self.assertEqual(rows[0]['INSPECTION_RESULT'], 'Pass')
        self.assertEqual(pages, 1)

    def test_peel_category_without_result_column(self):
        rows, _, _ = _peel_page(table([('abc','2026-10-08')], result=False), PEEL['table_url'])
        self.assertEqual(rows[0]['FACILITY_ID'], 'abc')
        self.assertNotIn('INSPECTION_RESULT', rows[0])

    def test_peel_full_scans_last_page_and_is_complete(self):
        h = PeelHttp({1:table([('a','2026-10-08')],1,2),2:table([('b','2025-01-01')],2,2)})
        snap = collect_peel_health(PEEL, h, False, force_full=True)
        self.assertEqual(len(snap.rows),2)
        self.assertTrue(snap.is_complete)
        self.assertEqual(h.posts[0][1]['data'], {'AcceptDisclaimerButton':'Accept'})

    def test_peel_recent_window_stops_and_does_not_remove_older_facility(self):
        h = PeelHttp({1:table([('a','2026-10-08')],1,3),2:table([('b','2026-09-29')],2,3)})
        snap = collect_peel_health(PEEL,h,False,smart=True,since_date='2026-10-01')
        self.assertFalse(snap.is_complete)
        self.assertEqual(len(snap.rows),1)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); con=open_db(p/'x.sqlite')
            try:
                process_snapshot(con,Snapshot(PEEL,[*snap.rows,{**snap.rows[0],'FACILITY_ID':'older','FACILITY_NAME':'Old'}],b'','x',{}),p/'raw')
                result=process_snapshot(con,snap,p/'raw')
                self.assertEqual(result['removed'],0)
            finally: con.close()

    def test_peel_limit_or_repeated_page_is_a_failure(self):
        for source,pages in [({**PEEL,'max_pages':1},{1:table([('a','2026-10-08')],1,2)}),
                             (PEEL,{1:table([('a','2026-10-08')],1,2),2:table([('a','2026-10-08')],2,2)})]:
            with self.assertRaises(RuntimeError):
                collect_peel_health(source,PeelHttp(pages),False,force_full=True)

    def test_peel_sort_must_be_honoured(self):
        with self.assertRaises(RuntimeError):
            collect_peel_health(PEEL,PeelHttp({1:table([('a','2026-10-08')],sort=False)}),False,smart=True,since_date='2026-10-01')

    def test_skipped_poll_retains_event_date_and_last_fetch(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); con=open_db(p/'x.sqlite')
            try:
                register_sources(con,[AGCO])
                snap=collect_web_table(AGCO,CsvHttp(),False)
                process_snapshot(con,snap,p/'raw')
                skipped=collect_web_table(AGCO,CsvHttp(),False,smart=True,previous_metadata=snap.metadata)
                process_snapshot(con,skipped,p/'raw')
                status=source_status(con)[0]
                self.assertEqual(status['latest_source_date'],'2026-10-01')
                self.assertTrue(status['last_data_fetch'])
                self.assertEqual(con.execute('select count(*) from changes').fetchone()[0],0)
            finally: con.close()

    def test_v04_existing_source_definitions_are_preserved(self):
        old=json.loads((ROOT/'tests/fixtures/v04_sources.json').read_text())
        current={s['id']:s for s in SOURCES}
        for s in old:
            if s['id'].startswith('agco_'): continue
            self.assertEqual(s,current[s['id']])
            self.assertEqual(source_universe_hash(s),source_universe_hash(current[s['id']]))


if __name__=='__main__': unittest.main()
