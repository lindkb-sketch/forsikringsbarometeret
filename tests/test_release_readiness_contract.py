"""Legacy entrypoint must not pass on a company-name-only checklist."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_release_readiness import validate


class ReleaseReadinessContract(unittest.TestCase):
    def test_historical_presence_and_green_ci_do_not_certify(self):
        payload = {'reference_quarter': 'Q3 2026', 'companies': [
            {'company': name} for name in
            ('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')]}
        self.assertFalse(validate(payload))

    def test_missing_one_metric_prevents_readiness(self):
        complete = {'financial_quarter_complete': True, 'all_seven_automated': True,
                    'definitions_comparable': True, 'market_data_fresh': True,
                    'investor_ready': True,
                    'status': 'automated_checks_passed_review_required'}
        self.assertTrue(validate(complete))
        for key in ('financial_quarter_complete', 'all_seven_automated',
                    'definitions_comparable', 'market_data_fresh', 'investor_ready'):
            self.assertFalse(validate(dict(complete, **{key: False})), key)
        self.assertFalse(validate(dict(complete, status='NOT_APPROVED_FOR_INVESTOR_USE')))


if __name__ == '__main__':
    unittest.main()
