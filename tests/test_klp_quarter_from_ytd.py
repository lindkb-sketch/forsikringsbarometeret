import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from klp_quarter_from_ytd import isolated


def row(q, revenue, claims, expenses, result):
    return {
        'company': 'KLP Skadeforsikring', 'year': 2026, 'quarter': q,
        'scope': 'group', 'currency': 'NOK', 'unit': 'NOK million',
        'revenue_definition': 'test revenue', 'claims_definition': 'test claims',
        'expenses_definition': 'test expenses',
        'source_url': 'https://www.klp.no/test.pdf', 'source_sha256': 'a'*64,
        'source_pages': [2, 3],
        'amounts': {'insurance_revenue': revenue, 'claims_cost': claims,
                    'operating_expenses': expenses, 'insurance_service_result': result},
    }


class KLPQuarterTests(unittest.TestCase):
    def test_q1_equals_cumulative(self):
        q = isolated(row(1, 100, 70, 15, 15))
        self.assertEqual(q['amounts']['insurance_revenue'], 100)
        self.assertEqual(q['ratios']['combined_ratio'], 85)

    def test_q3_ratio_is_not_difference_of_ytd_percentages(self):
        q = isolated(row(3, 360, 252, 54, 54), row(2, 200, 150, 30, 20))
        self.assertEqual(q['amounts']['insurance_revenue'], 160)
        self.assertAlmostEqual(q['ratios']['loss_ratio'], 63.75)
        self.assertAlmostEqual(q['ratios']['expense_ratio'], 15)
        self.assertAlmostEqual(q['ratios']['combined_ratio'], 78.75)

    def test_wrong_year_rejected(self):
        old = row(2, 200, 150, 30, 20)
        old['year'] = 2025
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            isolated(row(3, 360, 252, 54, 54), old)

    def test_missing_prior_quarter_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Previous'):
            isolated(row(3, 360, 252, 54, 54))

    def test_nonmatching_basis_rejected(self):
        old = row(2, 200, 150, 30, 20)
        old['scope'] = 'norway'
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            isolated(row(3, 360, 252, 54, 54), old)

    def test_no_subtraction_of_roe_or_solvency(self):
        current = row(3, 360, 252, 54, 54)
        current['return_on_equity'] = 12
        current['solvency_ratio'] = 200
        result = isolated(current, row(2, 200, 150, 30, 20))
        self.assertNotIn('return_on_equity', result['ratios'])
        self.assertNotIn('solvency_ratio', result['ratios'])


if __name__ == '__main__':
    unittest.main()
