"""Regression tests for the nine-insurer evidence gate."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_extended_insurer_evidence import validate, COMPANIES, REQUIRED


def fixture():
    return (
        {'insurers': {
            'Alm. Brand': {'status': 'verified_issuer_announcement',
                           'source_type': 'official_issuer_interim_announcement',
                           'source_url': 'https://investorrelations.almbrand.dk/report',
                           'year': 2026, 'quarter': 3,
                           'metrics': {key: 1.0 for key in REQUIRED}},
            'KLP Skadeforsikring': {
                'status': 'awaiting_source_verified_metrics', 'metrics': {}}}},
        {'sources': [{'company': company} for company in COMPANIES]},
        {company: {'events': []} for company in COMPANIES},
    )


class EvidenceGateTests(unittest.TestCase):
    def test_valid_partial_onboarding(self):
        self.assertEqual(validate(*fixture()), [])

    def test_missing_ninth_source_fails(self):
        data, sources, calendar = fixture()
        sources['sources'] = [x for x in sources['sources']
                              if x['company'] != 'KLP Skadeforsikring']
        self.assertTrue(validate(data, sources, calendar))

    def test_klp_unverified_values_fail(self):
        data, sources, calendar = fixture()
        data['insurers']['KLP Skadeforsikring']['metrics'] = {'combined_ratio': 90}
        self.assertTrue(validate(data, sources, calendar))

    def test_alm_brand_pdf_claim_without_pdf_fails(self):
        data, sources, calendar = fixture()
        data['insurers']['Alm. Brand']['source_type'] = 'official_quarterly_report'
        self.assertTrue(validate(data, sources, calendar))

    def test_missing_alm_metric_fails(self):
        data, sources, calendar = fixture()
        data['insurers']['Alm. Brand']['metrics'].pop('loss_ratio')
        self.assertTrue(validate(data, sources, calendar))


if __name__ == '__main__':
    unittest.main()
