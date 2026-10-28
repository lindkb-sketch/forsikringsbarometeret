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

class SplitHeaderPage:
    def extract_text(self, layout=False):
        return """Quarterly outline - Geography
DKKm Q3 Q2 Q1 Q4 Q3
2025 2025 2025 2024 2024
Danish general insurance
Insurance revenue 4633 4667 4629 4556 4609
Norwegian general insurance
NOK/DKK, average rate for the period 63.32 64.49 63.39 63.24 64.18
Insurance revenue 2222 2175 2059 2125 2083
Insurance service result 375 389 96 130 311
Claims ratio, net of reinsurance 71.1 70.1 82.8 80.3 72.5
Expense ratio 12.0 12.0 12.5 13.6 12.5
Combined ratio 83.1 82.1 95.3 93.9 85.0
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

    @patch("tryg_norway_pdf.pdfplumber.open")
    def test_separate_quarter_and_year_lines(self, opener):
        fake=Pdf()
        fake.pages=[SplitHeaderPage()]
        opener.return_value=fake
        rows=parse_norway_pdf(b"%PDF-example",2025,3,"https://tryg.com/report.pdf")
        lookup={(r["year"],r["metric"]):r["value"] for r in rows}
        self.assertEqual(lookup[(2025,"insurance_revenue")],2222)
        self.assertEqual(lookup[(2024,"insurance_revenue")],2083)
        self.assertEqual(lookup[(2025,"insurance_service_result")],375)

if __name__=="__main__":
    unittest.main()
