import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from tryg_norway_pdf import parse_norway_pdf

class Page:
    def extract_text(self, layout=False):
        return """Quarterly outline - Geography
DKKm Q3 2025 Q3 2024
Danish general insurance
Insurance revenue 4633 4609
Norwegian general insurance
Insurance revenue 2222 2083
Insurance service result 375 311
Claims ratio, net of reinsurance 71.1 72.5
Expense ratio 12.0 12.5
Combined ratio 83.1 85.0
"""

class Pdf:
    pages = [Page()]
    def __enter__(self):return self
    def __exit__(self,*args):return False

class TestTrygPdfGeography(unittest.TestCase):
    @patch("tryg_norway_pdf.pdfplumber.open", return_value=Pdf())
    def test_norway_q3_and_prior_comparison(self, _):
        rows=parse_norway_pdf(b"%PDF-example",2025,3,"https://tryg.com/report.pdf")
        by={(r["year"],r["metric"]):r for r in rows}
        self.assertEqual(by[(2025,"insurance_revenue")]["value"],2222)
        self.assertEqual(by[(2024,"insurance_revenue")]["value"],2083)
        self.assertEqual(by[(2025,"combined_ratio")]["value"],83.1)
        self.assertIn("Norwegian general insurance",by[(2025,"combined_ratio")]["source_section"])
        self.assertEqual(len(rows),10)

if __name__=="__main__":
    unittest.main()
