"""Source-traced, future-quarter, freshness and fail-closed readiness contracts."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from investor_readiness import COMPANIES, REQUIRED, make, provenance_valid


def row(company, year, quarter, metric):
    return {'company': company, 'year': year, 'quarter': quarter,
            'scope': 'group', 'period_type': 'quarter', 'metric': metric,
            'value': 80.0, 'status': 'reported',
            'unit': 'percent' if 'ratio' in metric else 'MNOK',
            'source_page': 4, 'source_url': 'https://issuer.example/official.pdf'}


class InvestorReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.rows = [row(c, 2026, 3, m) for c in COMPANIES for m in REQUIRED]
        self.calendar = {c: {'events': []} for c in COMPANIES}
        self.coverage = {'companies': [{'company': c, 'automatic_complete': True} for c in COMPANIES]}
        self.stocks = {'prices': {c: {'trading_date': '2026-10-23', 'close': 120.0}
                                 for c in ('Gjensidige','Protector','Storebrand','Tryg','Sampo / If')}}
        self.news = {'items': [{'approved': True, 'published_at': '2026-10-23T07:00:00Z'}]}

    def report(self, today=dt.date(2026, 10, 23)):
        inputs = {'verified_financial_feed': {'observations': self.rows},
                  'report_coverage': self.coverage, 'calendar': self.calendar,
                  'stock_prices': self.stocks, 'official_news': self.news}
        for name, obj in inputs.items():
            (self.root / 'data' / (name + '.json')).write_text(json.dumps(obj))
        return make(self.root, today=today)

    def test_all_metrics_with_sources_pass_automated_checks(self):
        r = self.report()
        self.assertTrue(r['financial_quarter_complete'])
        self.assertTrue(r['investor_ready'])
        self.assertEqual(r['status'], 'automated_checks_passed_review_required')

    def test_missing_future_report_keeps_previous_quarter_only(self):
        self.rows = [x for x in self.rows if x['company'] != 'Sampo']
        self.rows += [row('Sampo', 2026, 2, m) for m in REQUIRED]
        self.calendar['Sampo / If'] = {'events': [{'period': 'Q3 2026', 'date': '2026-11-04'}]}
        r = self.report()
        item = next(x for x in r['companies'] if x['company'] == 'Sampo')
        self.assertEqual(item['status'], 'awaiting_official_publication')
        self.assertEqual(item['latest_source_located_quarter'], 'Q2 2026')
        self.assertEqual(len(item['missing_metrics']), 5)
        self.assertFalse(r['investor_ready'])

    def test_overdue_or_unknown_date_not_mistaken_for_published(self):
        self.rows = [x for x in self.rows if x['company'] not in ('Sampo', 'Frende')]
        self.calendar['Sampo / If'] = {'events': [{'period': 'Q3 2026', 'date': '2026-10-20'}]}
        states = {x['company']: x['status'] for x in self.report()['companies']}
        self.assertEqual(states['Sampo'], 'missing_after_calendar_date')
        self.assertEqual(states['Frende'], 'report_date_unconfirmed')

    def test_provenance_missing_page_blocks_financial_completeness(self):
        for x in self.rows:
            if x['company'] == 'Tryg' and x['metric'] == 'combined_ratio':
                del x['source_page']
        r = self.report()
        item = next(x for x in r['companies'] if x['company'] == 'Tryg')
        self.assertIn('combined_ratio', item['invalid_metrics'])
        self.assertFalse(r['financial_quarter_complete'])

    def test_apm_revenue_is_not_assumed_ifrs_comparable(self):
        for x in self.rows:
            if x['company'] == 'Storebrand' and x['metric'] == 'insurance_revenue':
                x['source_definition'] = 'Insurance segment premiums f.o.a.; not IFRS insurance revenue'
        r = self.report()
        self.assertFalse(r['definitions_comparable'])
        self.assertFalse(r['investor_ready'])

    def test_stale_stock_and_no_headlines_fail_freshness(self):
        self.stocks['prices']['Tryg']['trading_date'] = '2026-09-01'
        self.news['items'] = []
        r = self.report()
        self.assertFalse(r['market_data_fresh'])
        self.assertFalse(r['news']['recent_attributed_headlines'])

    def test_simulated_2027_q1_rollover_does_not_reuse_2026_q3(self):
        self.rows += [row('Fremtind', 2027, 1, m) for m in REQUIRED]
        r = self.report(dt.date(2027, 4, 15))
        self.assertEqual(r['reference_quarter'], 'Q1 2027')
        self.assertFalse(r['financial_quarter_complete'])
        self.assertEqual(next(x for x in r['companies'] if x['company'] == 'Gjensidige')['status'],
                         'report_date_unconfirmed')

    def test_future_ytd_must_not_be_misread_as_quarter(self):
        # A current Q1 group observation for another insurer advances the
        # global period, but Sampo has only a YTD figure, not a Q1 quarter.
        self.rows.append(row('Fremtind', 2027, 1, 'combined_ratio'))
        self.rows.append(dict(row('Sampo', 2027, 1, 'insurance_revenue'),
                              period_type='ytd'))
        r = self.report(dt.date(2027, 4, 15))
        self.assertEqual(r['reference_quarter'], 'Q1 2027')
        self.assertNotEqual(next(x for x in r['companies'] if x['company'] == 'Sampo')['status'],
                            'source_located_quarter')

    def test_invalid_source_location_or_nan_is_rejected(self):
        x = row('Tryg', 2026, 3, 'insurance_revenue')
        x['source_page'] = 0
        self.assertFalse(provenance_valid(x))
        x['source_page'] = 4
        x['value'] = float('nan')
        self.assertFalse(provenance_valid(x))

    def test_real_repository_is_not_falsely_investor_certified(self):
        r = make(Path(__file__).resolve().parents[1])
        self.assertEqual(len(r['companies']), 7)
        if not r['all_seven_automated']:
            self.assertFalse(r['investor_ready'])


if __name__ == '__main__':
    unittest.main()
