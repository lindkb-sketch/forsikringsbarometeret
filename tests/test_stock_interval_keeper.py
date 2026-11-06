"""Self-replenishing quote interval is bounded, de-duplicated and Pages-unlocked."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from continue_stock_interval import continue_interval, parse_start

UTC = dt.timezone.utc


class StockIntervalKeeperTests(unittest.TestCase):
    def test_waits_until_fifteen_minutes_after_run_started(self):
        now = [dt.datetime(2026, 11, 6, 9, 17, tzinfo=UTC)]
        waits, called = [], []
        def fake_sleep(seconds):
            waits.append(seconds)
            now[0] += dt.timedelta(seconds=seconds)
        def dispatch(now):
            called.append(now)
            return 'dispatched'
        result = continue_interval('2026-11-06T09:15:00Z',
                                   clock=lambda: now[0], sleeper=fake_sleep,
                                   dispatcher=dispatch)
        self.assertEqual(result, 'dispatched')
        self.assertEqual(waits, [780])
        self.assertEqual(called, [dt.datetime(2026, 11, 6, 9, 30, tzinfo=UTC)])

    def test_late_wake_does_not_sleep_again(self):
        now = dt.datetime(2026, 11, 6, 10, 20, tzinfo=UTC)
        result = continue_interval('2026-11-06T10:00:00Z',
                     clock=lambda: now, sleeper=lambda _: self.fail('unexpected wait'),
                     dispatcher=lambda **_: 'recent')
        self.assertEqual(result, 'recent')

    def test_active_newer_stock_job_is_not_duplicated(self):
        now = dt.datetime(2026, 11, 6, 10, 20, tzinfo=UTC)
        result = continue_interval('2026-11-06T10:00:00Z',
                     clock=lambda: now, sleeper=lambda _: self.fail('unexpected wait'),
                     dispatcher=lambda **_: 'active')
        self.assertEqual(result, 'active')

    def test_stop_after_market_close_and_on_weekends(self):
        for start, now in [('2026-11-06T17:00:00Z', '2026-11-06T17:01:00Z'),
                           ('2026-11-07T09:00:00Z', '2026-11-07T09:01:00Z')]:
            with self.subTest(start=start):
                instant = dt.datetime.fromisoformat(now.replace('Z', '+00:00'))
                result = continue_interval(start, clock=lambda: instant,
                            sleeper=lambda _: self.fail('closed market waited'),
                            dispatcher=lambda **_: self.fail('closed market dispatched'))
                self.assertEqual(result, 'closed')

    def test_refuse_bad_and_future_timestamps(self):
        for value in ('', 'not-a-date', '2026-11-06T10:00:00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_start(value)
        with self.assertRaisesRegex(ValueError, 'unreasonably far'):
            continue_interval('2026-11-06T11:00:00Z',
                     clock=lambda: dt.datetime(2026, 11, 6, 10, 30, tzinfo=UTC),
                     sleeper=lambda _: None, dispatcher=lambda **_: 'dispatched')

    def test_own_keeper_lock_does_not_hold_finance_pages_lock(self):
        workflow = (ROOT / '.github/workflows/scheduled-import-watchdog.yml').read_text()
        self.assertIn('workflow_run:', workflow)
        self.assertIn('types: [completed]', workflow)
        self.assertIn('Oppdater forsinkede aksjekurser (egen pipeline)', workflow)
        self.assertIn('github.event.workflow_run.created_at', workflow)
        self.assertIn('github.event.workflow_run.repository.full_name == github.repository', workflow)
        self.assertIn('python scripts/continue_stock_interval.py', workflow)
        self.assertIn('cancel-in-progress: true', workflow)
        self.assertIn("github.event_name != 'workflow_run'", workflow)
        self.assertNotIn('forsikringsbarometeret-publish', workflow)


if __name__ == '__main__':
    unittest.main()
