"""Conservative checks for missing quarterly KPI coverage across nine insurers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from quarterly_kpi_completeness import build, COMPANIES, METRICS

class KPICompletenessTests(unittest.TestCase):
    def fixture(self):
        return {'companies': [
            {'company': name, 'period': 'Q3 2026', 'status': 'verified_quarterly_feed',
             'source_url': 'https://issuer.example/report.pdf',
             'metrics': {key: 1.0 for key in METRICS}}
            for name in COMPANIES
        ]}

    def test_complete_does_not_claim_unattended_ingestion(self):
        report = build(self.fixture())
        self.assertTrue(report['all_nine_metrics_present'])
        self.assertFalse(report['all_nine_unattended_extraction_verified'])
        self.assertTrue(all(not r['unattended_extraction_verified'] for r in report['companies']))

    def test_null_stays_missing_not_zero(self):
        data = self.fixture()
        data['companies'][0]['metrics']['profit_before_tax'] = None
        report = build(data)
        self.assertFalse(report['all_nine_metrics_present'])
        self.assertEqual(report['companies'][0]['missing_metrics'], ['profit_before_tax'])
        self.assertIn('combined_ratio', report['companies'][0]['present_metrics'])

    def test_reporting_exceptions_do_not_count_as_missing(self):
        data = self.fixture()
        for row in data['companies']:
            if row['company'] in ('Frende', 'KLP Skadeforsikring'):
                row['metrics']['return_on_equity'] = None
            if row['company'] == 'Frende':
                row['metrics']['solvency_ratio'] = None
        report = build(data)
        self.assertTrue(report['all_nine_metrics_present'])
        frende = next(r for r in report['companies'] if r['company'] == 'Frende')
        self.assertEqual(set(frende['not_reported_metrics']), {'return_on_equity', 'solvency_ratio'})
        self.assertEqual(frende['expected_count'], 7)

    def test_missing_company_fails_closed(self):
        data = self.fixture()
        data['companies'].pop()
        with self.assertRaisesRegex(ValueError, 'exactly nine'):
            build(data)

    def test_unknown_metric_fails_closed(self):
        data = self.fixture()
        data['companies'][0]['metrics']['made_up_kpi'] = 1
        with self.assertRaisesRegex(ValueError, 'unknown metrics'):
            build(data)

if __name__ == '__main__':
    unittest.main()
