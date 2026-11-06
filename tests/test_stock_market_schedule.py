"""Fast tests of stock-only schedule and data-publishing safety."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from stock_market_window import should_poll
from update_stock_prices import update, SYMBOLS, MARKETS
from verify_stock_feed import validate

UTC=dt.timezone.utc

class IndependentStockScheduleTests(unittest.TestCase):
    def test_trading_windows_are_timezone_aware_in_both_seasons(self):
        self.assertTrue(should_poll(dt.datetime(2026,11,3,9,tzinfo=UTC)))
        self.assertTrue(should_poll(dt.datetime(2026,7,6,7,tzinfo=UTC)))
        self.assertFalse(should_poll(dt.datetime(2026,11,3,3,tzinfo=UTC)))
        self.assertFalse(should_poll(dt.datetime(2026,11,3,20,tzinfo=UTC)))
        self.assertFalse(should_poll(dt.datetime(2026,11,7,9,tzinfo=UTC)))
        with self.assertRaisesRegex(ValueError,'timezone-aware'):
            should_poll(dt.datetime(2026,11,3,9))

    def test_workflow_is_independent_and_serialized_with_financial_publish(self):
        quote=(ROOT/'.github/workflows/stock-prices.yml').read_text()
        financial=(ROOT/'.github/workflows/update.yml').read_text()
        self.assertIn("cron: '7,22,37,52 6-18 * * 1-5'",quote)
        self.assertIn('forsikringsbarometeret-publish',quote)
        self.assertIn('forsikringsbarometeret-publish',financial)
        self.assertIn("paths-ignore:",financial)
        self.assertIn("'data/stock_prices.json'",financial)
        self.assertNotIn('python scripts/run_pipeline.py',quote)
        self.assertNotIn('python scripts/update_stock_prices.py',financial)
        self.assertIn('verify_public_stock_prices.py',quote)

    def test_both_publishers_use_multi_pending_fifo_queue_and_same_lock(self):
        quote=(ROOT/'.github/workflows/stock-prices.yml').read_text(encoding='utf-8')
        finance=(ROOT/'.github/workflows/update.yml').read_text(encoding='utf-8')
        # Stock retains its short top-level lock; finance takes the same lock
        # only after preparing and auditing the snapshot.
        self.assertNotIn('\nconcurrency:', '\n'+finance)
        concurrency_quote=quote.split('concurrency:',1)[1].split('jobs:',1)[0]
        concurrency_finance=finance.split('  publish:',1)[1].split('    steps:',1)[0]
        for name,concurrency in (('stock',concurrency_quote),('financial',concurrency_finance)):
            self.assertIn('group: forsikringsbarometeret-publish',concurrency,name)
            self.assertIn('queue: max',concurrency,name)
            self.assertIn('cancel-in-progress: false',concurrency,name)
            self.assertNotIn('cancel-in-progress: true',concurrency,name)
        self.assertIn('actions/deploy-pages@v4',quote)
        self.assertIn('actions/deploy-pages@v4',finance)

    def test_quote_poll_reusing_same_source_data_does_not_rewrite_file(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'prices.json'
            now=dt.datetime(2026,11,3,12,0,tzinfo=UTC)
            def quote(symbol):
                suffix=next(s for s in MARKETS if symbol.endswith(s))
                return {'symbol':symbol,'currency':MARKETS[suffix][2],
                    'close':102.5,'trading_date':'2026-11-03',
                    'previous_close':101,'previous_close_date':'2026-11-02',
                    'observed_at':now.isoformat(),
                    'history':[{'date':'2026-11-02','price':101},
                               {'date':'2026-11-03','price':102.5}],
                    'availability':'available','source_url':'https://example.org/source',
                    'price_type':'delayed_daily_observation'}
            first=update(fetcher=quote,out=file,now=now)
            contents=file.read_bytes()
            second=update(fetcher=quote,out=file,now=now+dt.timedelta(minutes=15))
            self.assertEqual(first['updated_at'],second['updated_at'])
            self.assertEqual(file.read_bytes(),contents)
            self.assertEqual(validate(json.loads(file.read_text()))['active_quotes'],5)

    def test_bad_quotes_do_not_pass_publication_gate(self):
        with self.assertRaisesRegex(ValueError,'No fresh valid stock'):
            validate({'prices':{},'unlisted':['Fremtind','Frende']})

if __name__=='__main__':
    unittest.main()
