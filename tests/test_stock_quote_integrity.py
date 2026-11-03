"""Stock dashboard must never render hardcoded quotes or silently stale prices."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from update_stock_prices import normalize,update,SYMBOLS

class MarketDataTests(unittest.TestCase):
    def payload(self,symbol='GJF.OL',currency='NOK',values=(100,105)):
        return {'chart':{'result':[{
            'meta':{'symbol':symbol,'currency':currency,
                    'regularMarketTime':1793709000,
                    'currentTradingPeriod':{'regular':{'end':1793718000}}},
            'timestamp':[1793610000,1793696400],
            'indicators':{'quote':[{'close':list(values)}]}
        }]}}
    def test_daily_series_preserves_actual_source_values(self):
        data=normalize('GJF.OL',self.payload())
        self.assertEqual(data['symbol'],'GJF.OL')
        self.assertEqual(data['exchange'],'Oslo Børs')
        self.assertEqual([r['price'] for r in data['history']],[100,105])
        self.assertEqual(data['close'],data['history'][-1]['price'])
        self.assertEqual(data['previous_close'],100)
        self.assertTrue(data['observed_at'].endswith('+00:00'))
    def test_invalid_quotes_are_rejected_not_substituted(self):
        with self.assertRaisesRegex(ValueError,'Ticker'):
            normalize('GJF.OL',self.payload(symbol='PROT.OL'))
        with self.assertRaisesRegex(ValueError,'currency'):
            normalize('GJF.OL',self.payload(currency='EUR'))
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            normalize('GJF.OL',self.payload(values=(None,0)))
    def test_provider_error_preserves_old_quote_only_as_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'stocks.json'
            now=dt.datetime.now(dt.timezone.utc)
            snapshot=normalize('GJF.OL',self.payload())
            path.write_text(json.dumps({'prices':{'Gjensidige':snapshot}}))
            result=update(fetcher=lambda symbol: (_ for _ in ()).throw(
                ValueError('provider unavailable')),out=path,now=now)
            self.assertEqual(result['prices']['Gjensidige']['availability'],'stale')
            self.assertEqual(result['prices']['Gjensidige']['stale_reason'],'provider unavailable')
            self.assertNotIn('Tryg',result['prices'])
            self.assertEqual(set(result['errors']),set(SYMBOLS))
    def test_no_embedded_stock_history_or_fallback_svg_in_public_html(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        for forbidden in ('stockFallback','embeddedStockSvgs',
                          'Månedssluttkurser fra 2026',
                          '01.01–19.10.2026','stockCsvInput('):
            self.assertNotIn(forbidden,html)
        self.assertIn("quote?.availability==='available'",html)
        self.assertIn("stockCSV[c]=history.map(",html)
    def test_browser_quote_validation_accepts_iso_date_regex(self):
        browser=(ROOT/'tests/live_browser_e2e.cjs').read_text(encoding='utf-8')
        self.assertIn(r'/^\d{4}-\d{2}-\d{2}$/',browser)
        self.assertNotIn(r'/^\\d{4}-\\d{2}-\\d{2}$/',browser)
    def test_stock_refresh_is_independent_of_quarterly_pipeline(self):
        workflow=(ROOT/'.github/workflows/stock-prices.yml').read_text(encoding='utf-8')
        quarterly=(ROOT/'.github/workflows/update.yml').read_text(encoding='utf-8')
        self.assertIn('python scripts/update_stock_prices.py',workflow)
        self.assertIn('python scripts/verify_stock_feed.py',workflow)
        self.assertIn('actions/deploy-pages@v4',workflow)
        self.assertIn('forsikringsbarometeret-publish',workflow)
        self.assertNotIn('python scripts/update_stock_prices.py',quarterly)
        self.assertIn("'data/stock_prices.json'",quarterly)

if __name__=='__main__':
    unittest.main()
