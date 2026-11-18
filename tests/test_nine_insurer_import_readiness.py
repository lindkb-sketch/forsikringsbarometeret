"""Tests for conservative PDF discovery and nine-company comparison."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from import_extended_pdfs import approved, candidates, inspect_pdf
from build_nine_insurer_comparison import build, COMPANIES


class NineInsurerReadinessTests(unittest.TestCase):
    def test_pdf_host_allowlist(self):
        self.assertTrue(approved('https://www.klp.no/report.pdf', 'KLP Skadeforsikring'))
        self.assertFalse(approved('https://www.klp.no.evil.test/report.pdf', 'KLP Skadeforsikring'))
        self.assertFalse(approved('http://www.klp.no/report.pdf', 'KLP Skadeforsikring'))

    def test_discovery_rejects_external_and_non_pdf(self):
        html = '<a href="/q3.pdf">report</a><a href="https://evil.test/q3.pdf">bad</a><a href="/page">page</a>'
        self.assertEqual(candidates(html, 'https://www.klp.no/', 'KLP Skadeforsikring'),
                         ['https://www.klp.no/q3.pdf'])

    def test_comparison_has_nine_without_fabricating_klp(self):
        data = build({'observations': []}, {'insurers': {
            'KLP Skadeforsikring': {'status': 'awaiting_source_verified_metrics', 'metrics': {}},
            'Alm. Brand': {'status': 'verified_issuer_announcement', 'year': 2026,
                           'quarter': 3, 'currency': 'DKK', 'source_url': 'https://example.test',
                           'metrics': {'combined_ratio': 75.3}}}})
        self.assertEqual(len(data['companies']), 9)
        self.assertEqual({x['company'] for x in data['companies']}, set(COMPANIES))
        klp = next(x for x in data['companies'] if x['company'] == 'KLP Skadeforsikring')
        self.assertTrue(all(v is None for v in klp['metrics'].values()))
        self.assertFalse(data['investor_use_approved'])

    def test_unapproved_pdf_rejected_before_parsing(self):
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            inspect_pdf(b'%PDF-test', 'Alm. Brand', 'https://evil.test/a.pdf')


if __name__ == '__main__':
    unittest.main()
