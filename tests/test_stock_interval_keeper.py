"""A lost cron slot must be recovered without unbounded/duplicate requests."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from continue_stock_interval import continue_interval, parse_start

UTC = dt.timezone.utc


class StockIntervalKeeperTests(unittest.TestCase):
    def test_sleeps_until_fifteen_minutes_after_stock_started(self):
        now = [dt.datetime(2026, 11, 6, 9, 17, tzinfo=UTC)]
        waits, called = [], []
        def fake_sleep(seconds):
            waits.append(seconds)
            now[0] += dt.timedelta(seconds=seconds)
        def checker(now):
            called.append(now)
            return 'dispatched'
        result = continue_interval('2026-11-06T09:15:00Z',
                                   clock=lambda: now[0], sleeper=fake_sleep,
                                   dispatcher=checker)
        self.assertEqual(result, 'dispatched')
        self.assertEqual(waits, [780])
        self.assertEqual(called, [dt.datetime(2026, 11, 6, 9, 30, tzinfo=UTC)])

    def test_next_run_is_noop_when_watchdog_finds_a_newer_run(self):
        now = dt.datetime(2026, 11, 6, 10, 20, tzinfo=UTC)
        self.assertEqual(continue_interval('2026-11-06T10:00:00Z',
                         clock=lambda: now, sleeper=lambda _: self.fail('late wake slept'),
                         dispatcher=lambda **_: 'recent'), 'recent')

    def test_a_newer_active_run_is_not_dispatched_again(self):
        now = dt.datetime(2026, 11, 6, 10, 20, tzinfo=UTC)
        self.assertEqual(continue_interval('2026-11-06T10:00:00Z',
                         clock=lambda: now, sleeper=lambda _: self.fail('unexpected sleep'),
                         dispatcher=lambda **_: 'active'), 'active')

    def test_no_weekend_or_after_market_close_requeue(self):
        for start, now in [('2026-11-06T17:00:00Z', '2026-11-06T17:01:00Z'),
                           ('2026-11-07T09:00:00Z', '2026-11-07T09:01:00Z')]:
            with self.subTest(start=start):
                current = dt.datetime.fromisoformat(now.replace('Z', '+00:00'))
                self.assertEqual(continue_interval(start, clock=lambda: current,
                                  sleeper=lambda _: self.fail('closed market slept'),
                                  dispatcher=lambda **_: self.fail('closed market dispatched')), 'closed')

    def test_rejects_invalid_or_future_timestamp(self):
        for value in ('', 'not-a-date', '2026-11-06T10:00:00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_start(value)
        with self.assertRaisesRegex(ValueError, 'unreasonably far'):
            continue_interval('2026-11-06T11:00:00Z',
                              clock=lambda: dt.datetime(2026, 11, 6, 10, 30, tzinfo=UTC),
                              sleeper=lambda _: None, dispatcher=lambda **_: 'dispatched')

    def test_explicit_repository_dispatch_not_suppressed_workflow_run(self):
        stock = (ROOT / '.github/workflows/stock-prices.yml').read_text()
        recurring = (ROOT / '.github/workflows/stock-recurring.yml').read_text()
        watchdog = (ROOT / '.github/workflows/scheduled-import-watchdog.yml').read_text()
        self.assertIn('python scripts/arm_stock_interval.py',stock)
        self.assertIn('always() && !cancelled()',stock)
        self.assertIn('group: forsikringsbarometeret-publish',stock)
        self.assertIn('repository_dispatch:',recurring)
        self.assertIn('types: [stock_next_check]',recurring)
        self.assertIn('github.event.client_payload.source_run_id',recurring)
        self.assertIn('python scripts/continue_stock_interval.py',recurring)
        self.assertIn('cancel-in-progress: true',recurring)
        self.assertNotIn('forsikringsbarometeret-publish',recurring)
        self.assertNotIn('actions/deploy-pages@',recurring)
        self.assertNotIn('workflow_run:',watchdog)
        self.assertIn('python scripts/check_stock_schedule.py',watchdog)

    def test_explicit_arm_posts_run_id_with_repository_dispatch(self):
        import json
        from arm_stock_interval import arm
        class Response:
            status=204
            def __enter__(self): return self
            def __exit__(self,*args): return False
        calls=[]
        def opener(req,timeout):
            calls.append(req)
            return Response()
        payload=arm('owner/repo','12345','test',opener=opener)
        self.assertEqual(payload,{'event_type':'stock_next_check','client_payload':{'source_run_id':'12345'}})
        self.assertEqual(calls[0].full_url,'https://api.github.com/repos/owner/repo/dispatches')
        self.assertEqual(json.loads(calls[0].data),payload)
        for bad in ('0','../123',''):
            with self.assertRaises(ValueError):arm('owner/repo',bad,'test',opener=opener)

    def test_source_stock_run_is_checked_against_github_api(self):
        import json
        from continue_stock_interval import fetch_stock_created_at
        data={'id':12345,'name':'Oppdater forsinkede aksjekurser (egen pipeline)',
              'head_branch':'main','created_at':'2026-11-06T09:15:00Z',
              'repository':{'full_name':'owner/repo'}}
        class Response:
            def __init__(self,body):self.body=body
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self):return json.dumps(self.body).encode('utf-8')
        self.assertEqual(fetch_stock_created_at('12345','owner/repo','test',
             opener=lambda *args,**kw:Response(data)),data['created_at'])
        for key,bad in (('id',99),('name','Other'),('head_branch','other')):
            with self.assertRaises(ValueError):
                fetch_stock_created_at('12345','owner/repo','test',
                    opener=lambda *args,**kw:Response({**data,key:bad}))


if __name__ == '__main__':
    unittest.main()
