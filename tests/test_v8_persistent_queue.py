"""Regression coverage for all-project DeepSeek investigation and durable backlog."""
import csv
from contextlib import closing
import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path

import v8_ai_queue as queue
import v8_deepseek_native as deepseek

FIXED = dt.date(2026, 10, 19)


def make_row(number, lane='PERMIT_REVIEW'):
    return {
        'project_id': 'project-' + str(number),
        'address': str(100 + number) + ' Test Road, Toronto',
        'description': 'Commercial renovations and fit out at this address',
        'source_id': 'toronto_building_permits',
        'source_keys': 'permit-' + str(number),
        'current_source_status': 'Under review',
        'lane': lane,
        'review_priority': '75',
        'company_name': '',
    }


def export(path, records):
    fields = list(make_row(1))
    with Path(path).open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def api(path, payload):
    if path == '/v1/tools/search':
        return {'results': []}
    if path == '/chat/completions':
        return {
            'choices': [{'finish_reason': 'stop', 'message': {'content':
                '{"operator":"","developer":"","contact":"",'
                '"project_stage":"Application under review",'
                '"buyer_fit":"Potential commercial fit-out contractors",'
                '"next_verification":"Check official permit status",'
                '"caveats":"Only the source record is available","source_urls":[]}'}}],
            'usage': {'prompt_tokens': 400, 'completion_tokens': 110},
        }
    raise AssertionError('Unexpected provider request: ' + path)


class DurableResearchQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.source = self.folder / 'CANDIDATES_V4_ALL_REVIEW_ONLY.csv'

    def run_ai(self, today, limit=0):
        return deepseek.run(self.source, self.folder, key='test-only', transport=api,
                            max_projects=limit, today=today)

    def test_all_candidates_over_25_reach_flash_when_budget_allows(self):
        export(self.source, [make_row(n) for n in range(35)])
        state = self.run_ai(FIXED)
        self.assertEqual(state['ai_calls_succeeded'], 35)
        self.assertEqual(state['queue_initial_uninvestigated'], 0)
        self.assertEqual(state['queue_due'], 0)
        self.assertLessEqual(state['reserved_usd'], deepseek.DAILY_LIMIT)
        self.assertEqual(len(deepseek.read_csv(self.folder/'GTA_RADAR_V8_INVESTIGATIONS.csv')), 35)

    def test_unfinished_projects_survive_beyond_48_hour_export(self):
        export(self.source, [make_row(n) for n in range(3)])
        first = self.run_ai(FIXED, limit=1)
        self.assertEqual(first['ai_calls_succeeded'], 1)
        self.assertEqual(first['queue_initial_uninvestigated'], 2)
        self.assertEqual(first['queue_stop_reason'], 'OPTIONAL_RUN_LIMIT')
        self.assertTrue((self.folder/'GTA_RADAR_V8_PENDING_QUEUE.csv').is_file())

        # Next day, no longer in the rolling municipal export.
        export(self.source, [])
        second = self.run_ai(FIXED + dt.timedelta(days=1))
        self.assertEqual(second['ai_calls_succeeded'], 2)
        self.assertEqual(second['queue_initial_uninvestigated'], 0)
        rows = deepseek.read_csv(self.folder/'GTA_RADAR_V8_INVESTIGATIONS.csv')
        self.assertEqual(len(rows), 3)

    def test_budget_suspends_without_marking_records_investigated(self):
        export(self.source, [make_row(n) for n in range(3)])
        with closing(deepseek.v5._ledger(self.folder/'v5_ai_budget.sqlite')) as db:
            db.execute('INSERT INTO spends VALUES(?,?,?,?,?)',
                       (FIXED.isoformat(), 'prior', 0.995, 0.995, 'DONE'))
            db.commit()
        def unexpected(*args):
            self.fail('No provider calls permitted when the $1 cap is reached')
        state = deepseek.run(self.source, self.folder, key='test-only',
                             transport=unexpected, max_projects=0, today=FIXED)
        self.assertEqual(state['queue_stop_reason'], 'DAILY_USD_LIMIT')
        self.assertEqual(state['queue_total'], 3)
        self.assertEqual(state['queue_initial_uninvestigated'], 3)
        self.assertEqual(state['ai_calls_attempted'], 0)
        self.assertEqual(deepseek.read_csv(self.folder/'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv'),[])

    def test_duplicate_model_claim_skips_and_researches_later_projects(self):
        export(self.source, [make_row(n) for n in range(3)])
        with closing(deepseek.v5._ledger(self.folder/'v5_ai_budget.sqlite')) as db:
            db.execute('INSERT INTO spends VALUES(?,?,?,?,?)',
                       (FIXED.isoformat(),'M8:project-0',0.008,0.001,'DONE'))
            db.commit()
        paths=[]
        def tracked_api(path,payload):
            paths.append(path)
            return api(path,payload)
        first=deepseek.run(self.source,self.folder,key='test-only',transport=tracked_api,
                          max_projects=0,today=FIXED)
        self.assertEqual(first['queue_stop_reason'],'QUEUE_DRAINED')
        self.assertEqual(first['duplicate_model_skipped'],1)
        self.assertEqual(first['ai_calls_attempted'],2)
        self.assertEqual(first['ai_calls_succeeded'],2)
        self.assertEqual(paths.count('/chat/completions'),2)
        self.assertEqual(first['queue_initial_uninvestigated'],1)
        self.assertGreater(deepseek.DAILY_LIMIT-first['reserved_usd'],0.01)
        # A repeated same-day run should not issue search or Flash calls for
        # already-paid candidates, nor exhaust the queue prematurely.
        paths.clear()
        second=deepseek.run(self.source,self.folder,key='test-only',transport=tracked_api,
                           max_projects=0,today=FIXED)
        self.assertEqual(second['queue_stop_reason'],'QUEUE_DRAINED')
        self.assertEqual(second['duplicate_model_skipped'],3)
        self.assertEqual(second['ai_calls_attempted'],0)
        self.assertEqual(paths,[])

    def test_confirmed_usage_releases_only_excess_reservation(self):
        with closing(deepseek.v5._ledger(self.folder/'v5_ai_budget.sqlite')) as db:
            self.assertTrue(deepseek.ledger_claim(db,FIXED.isoformat(),'M8:p1',
                                                  deepseek.MODEL_RESERVE))
            deepseek.ledger_finish(db,FIXED.isoformat(),'M8:p1','DONE',0.0002)
            spent,actual=db.execute(
                "SELECT reserved,actual FROM spends WHERE candidate='M8:p1'"
            ).fetchone()
            self.assertAlmostEqual(actual,0.0002)
            self.assertAlmostEqual(spent,0.0006)
            self.assertGreater(spent,0)
            self.assertTrue(deepseek.ledger_claim(db,FIXED.isoformat(),'M8:p2',
                                                  deepseek.MODEL_RESERVE))

    def test_old_completed_calls_do_not_exhaust_today_at_reserved_rate(self):
        # Before this repair, 110 inexpensive completed calls used up a full
        # day because the software summed reserved dollars instead of actual.
        with closing(deepseek.v5._ledger(self.folder/'v5_ai_budget.sqlite')) as db:
            for i in range(110):
                db.execute('INSERT INTO spends VALUES(?,?,?,?,?)',
                           (FIXED.isoformat(), 'old-' + str(i), 0.008,
                            0.00035, 'DONE'))
            db.commit()
            effective,completed,unknown,nominal=deepseek.effective_spend(db,FIXED.isoformat())
            self.assertAlmostEqual(completed, 0.0385)
            self.assertAlmostEqual(effective, 0.0385)
            self.assertAlmostEqual(unknown,0)
            self.assertAlmostEqual(nominal,0.88)
        export(self.source, [make_row(n) for n in range(10)])
        result=self.run_ai(FIXED)
        self.assertEqual(result['ai_calls_succeeded'],10)
        self.assertEqual(result['queue_initial_uninvestigated'],0)
        self.assertLess(result['reserved_usd'],0.10)
        self.assertGreater(result['nominal_reservations_usd'],0.88)

    def test_unknown_costs_still_hold_reservations_until_reconciled(self):
        with closing(deepseek.v5._ledger(self.folder/'v5_ai_budget.sqlite')) as db:
            db.execute('INSERT INTO spends VALUES(?,?,?,?,?)',
                       (FIXED.isoformat(),'unknown-response',0.75,None,'ERROR'))
            db.execute('INSERT INTO spends VALUES(?,?,?,?,?)',
                       (FIXED.isoformat(),'done-with-no-usage',0.20,None,'DONE'))
            db.execute('INSERT INTO spends VALUES(?,?,?,?,?)',
                       (FIXED.isoformat(),'known-success',0.008,0.001,'DONE'))
            db.commit()
            effective,completed,unknown,nominal=deepseek.effective_spend(db,FIXED.isoformat())
            self.assertAlmostEqual(effective,0.951)
            self.assertAlmostEqual(completed,0.001)
            self.assertAlmostEqual(unknown,0.95)
            self.assertFalse(deepseek.ledger_claim(db,FIXED.isoformat(),'too-large',0.05))
            self.assertTrue(deepseek.ledger_claim(db,FIXED.isoformat(),'small',0.01))

    def test_published_cache_and_off_peak_flash_rates(self):
        usage={'prompt_tokens':1000,'prompt_cache_hit_tokens':800,
               'prompt_cache_miss_tokens':200,'completion_tokens':500}
        off=dt.datetime(2026,10,19,13,0,tzinfo=dt.timezone.utc)
        peak=dt.datetime(2026,10,19,8,0,tzinfo=dt.timezone.utc)
        self.assertAlmostEqual(deepseek.model_usage_cost(usage,off),
                               (800*.003+200*.15+500*.60)/1e6)
        self.assertAlmostEqual(deepseek.model_usage_cost(usage,peak),
                               (800*.006+200*.30+500*1.20)/1e6)
        self.assertIsNone(deepseek.model_usage_cost({},off))
        partial={'prompt_tokens':1000,'completion_tokens':500}
        self.assertAlmostEqual(deepseek.model_usage_cost(partial,off),
                               (1000*.15+500*.60)/1e6)
        incoherent=dict(usage,prompt_cache_hit_tokens=2000)
        self.assertAlmostEqual(deepseek.model_usage_cost(incoherent,off),
                               (1000*.15+500*.60)/1e6)

    def test_utc_evening_timestamp_uses_local_calendar_day(self):
        previous = {'researched_at': '2026-10-19T01:30:00+00:00'}
        eastern = dt.timezone(dt.timedelta(hours=-4))
        self.assertEqual(queue.local_attempt_date(previous, eastern),
                         dt.date(2026,10,18))
        previous['investigated_local_date'] = '2026-10-18'
        self.assertEqual(queue.local_attempt_date(previous),
                         dt.date(2026,10,18))

    def test_source_only_analysis_rechecks_later_without_rebuying_next_day(self):
        row = make_row(2)
        old = {'status':'AI_SOURCE_RECORD_REVIEW',
               'researched_at':'2026-10-19T10:30:00+00:00',
               'investigated_local_date':'2026-10-19',
               'input_fingerprint':queue.fingerprint(row)}
        waiting = queue.build([row], [], {'project-2':old},FIXED)
        self.assertEqual(queue.due(waiting, {'project-2':old},FIXED+dt.timedelta(days=1)),[])
        self.assertEqual(len(queue.due(waiting, {'project-2':old},FIXED+dt.timedelta(days=14))),1)

    def test_identical_evidence_backed_projects_are_not_paid_for_again(self):
        row = make_row(5)
        old = {'status':'AI_EVIDENCE_REVIEW','input_fingerprint':queue.fingerprint(row)}
        self.assertEqual(queue.build([row],[],{'project-5':old},FIXED),[])
        newer = dict(row, description='New issuance recorded for commercial works')
        self.assertEqual(len(queue.build([newer],[],{'project-5':old},FIXED)),1)

    def test_permit_first_and_old_watch_record_eventually_ages_forward(self):
        older = make_row(1,'SOURCE_UPDATE_WATCH')
        older['_queued_on'] = (FIXED-dt.timedelta(days=80)).isoformat()
        fresh = make_row(2,'PERMIT_REVIEW')
        fresh['_queued_on'] = FIXED.isoformat()
        ready = queue.due([fresh,older],{},FIXED)
        self.assertEqual(ready[0]['project_id'],'project-1')


if __name__ == '__main__':
    unittest.main()
