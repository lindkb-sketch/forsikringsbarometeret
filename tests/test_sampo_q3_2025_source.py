"""Sampo Q3 2025 source integrity regression (no hardcoded financial values)."""
import json
import unittest
from pathlib import Path

class TestSampoSource(unittest.TestCase):
    def test_q3_2025_source(self):
        rows = json.loads((Path(__file__).resolve().parents[1] / 'data/financial_observations.json').read_text())['observations']
        for metric in ('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio'):
            matches = [r for r in rows if r.get('company') == 'Sampo' and r.get('year') == 2025 and r.get('quarter') == 3 and r.get('scope') == 'group' and r.get('period_type') == 'quarter' and r.get('metric') == metric and r.get('status') == 'reported' and str(r.get('source_url','')).startswith('https://')]
            with self.subTest(metric=metric):
                self.assertEqual(len(matches), 1)
