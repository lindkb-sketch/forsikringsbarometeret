"""Check Tryg issuer discovery works for reports without Excel."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from discover_tryg import parse

class DiscoverTrygPDF(unittest.TestCase):
    def test_pdf_only_quarter_is_discovered(self):
        html='<a href="/media/q3-2026-interim-report.pdf">Q3 2026 interim report</a>'
        rows=parse(html,2026)
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]["year"],rows[0]["quarter"]),(2026,3))
        self.assertIn("report_pdf_url",rows[0])
        self.assertNotIn("workbook_url",rows[0])

    def test_other_year_not_misclassified(self):
        html='<a href="/media/q3-2025-interim-report.pdf">Q3 2025 interim report</a>'
        self.assertEqual(parse(html,2026),[])

if __name__=="__main__":
    unittest.main()
