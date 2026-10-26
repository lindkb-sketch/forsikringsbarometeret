"""Ensure no hardcoded profitability figures and year rollover gaps are visible."""
import json
import re
import unittest
from pathlib import Path
from scripts.audit_profitability_history import audit, window

ROOT = Path(__file__).resolve().parents[1]

class ProfitabilityHistoryAuditTests(unittest.TestCase):
    def test_rolling_year_boundaries(self):
        self.assertEqual(window(2026, 3), [(2025, 3), (2025, 4), (2026, 1), (2026, 2), (2026, 3)])
        self.assertEqual(window(2026, 4), [(2025, 4), (2026, 1), (2026, 2), (2026, 3), (2026, 4)])
        self.assertEqual(window(2027, 1), [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2027, 1)])
        self.assertEqual(window(2027, 2), [(2026, 2), (2026, 3), (2026, 4), (2027, 1), (2027, 2)])

    def test_missing_q4_is_not_filled_by_fallback(self):
        rows = []
        for metric in ('combined_ratio','loss_ratio','expense_ratio'):
            for year, quarter in ((2026, 1), (2026, 2), (2026, 3)):
                rows.append({'company':'Fremtind','scope':'group','period_type':'quarter',
                             'status':'reported','year':year,'quarter':quarter,
                             'metric':metric,'value':77.0,
                             'source_url':'https://example.org/official-report.pdf'})
        report = audit(rows, 2026, 3)
        self.assertEqual(report['window'], ['Q3 2025','Q4 2025','Q1 2026','Q2 2026','Q3 2026'])
        fremtind = report['companies'][0]
        self.assertEqual(fremtind['quarters'][1]['status'], 'missing_verified_source')
        self.assertTrue(all(q['verified'] for q in fremtind['quarters'][2:]))
        self.assertFalse(report['fully_covered'])

    def test_no_hardcoded_profitability_series(self):
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        start = html.index('const profitabilityQuarters=')
        end = html.index('function setProfitabilityCompany(', start)
        declarations = html[start:end]
        self.assertIn('const profitabilityQuarters=[];', declarations)
        self.assertNotRegex(declarations, r"'Q[1-4] 20\\d\\d'\\s*:\\s*[\\[{]")
        self.assertNotRegex(declarations, r'\\bvalue\\s*:\\s*\\d+')
        self.assertIn('const profitabilityVerified=Object.fromEntries(', declarations)
        self.assertIn('const profitabilityReturns=Object.fromEntries(', declarations)

    def test_active_chart_reads_verified_feed(self):
        runtime = (ROOT / 'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
        self.assertIn('profitabilityVerified[name]={};profitabilityReturns[name]={};', runtime)
        self.assertIn('profitabilityVerified[name][l]=[loss,cost,cr]', runtime)
        self.assertIn('issuerProfitabilityTimeline(profitabilityCompany)', runtime)

if __name__ == '__main__':
    unittest.main()
