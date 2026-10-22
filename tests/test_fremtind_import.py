import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_fremtind_holding import number, extract
from unittest.mock import patch

class FremtindImporterTests(unittest.TestCase):
    def test_number_formats(self):
        self.assertEqual(number("6 205"), 6205)
        self.assertEqual(number("73,0 %"), 73)
        self.assertEqual(number("-28"), -28)
    def test_invalid_values_rejected(self):
        for value in ("", "N/A", "1 2x", "1e20"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    number(value)
    def test_official_report_table_q1_and_ytd_q2(self):
        class Page:
            def __init__(self, text): self.text=text
            def extract_text(self): return self.text
        class PDF:
            def __init__(self, q):
                self.pages=[Page(f"Kvartalsrapport Q{q} 2026 Fremtind Holding"),Page("Innhold"),Page(
                    f"Resultatutvikling og nøkkeltall\\nMNOK Q{q} 2026 Q{q} 2025 FY2025\\n"
                    "Inntekter fra forsikringstjenester 6 205 5 769 23 510\\n"
                    "Resultat fra forsikringstjenester 1 256 843 4 520\\n"
                    "Skadeprosent, netto etter gjenforsikring (%) 58,5 % 63,9 % 58,8 %\\n"
                    "Kostnadsprosent (%) 21,2 % 21,5 % 21,9 %\\n"
                    "Combined ratio, netto etter gjenforsikring (%) 79,8 % 85,4 % 80,8 %"),Page("Notes")]
            def __enter__(self): return self
            def __exit__(self,*args): return False
        for q, period in [(1,"quarter"),(2,"ytd")]:
            with self.subTest(q=q), patch("import_fremtind_holding.pdfplumber.open",return_value=PDF(q)):
                rows=extract(b"%PDF-test","https://cdn.sanity.io/files/report.pdf")
                values={r["metric"]:r["value"] for r in rows}
                self.assertEqual(values["insurance_revenue"],6205)
                self.assertEqual(values["insurance_service_result"],1256)
                self.assertEqual(values["combined_ratio"],79.8)
                self.assertEqual({r["period_type"] for r in rows},{period})
    def test_non_pdf_rejected(self):
        with self.assertRaises(Exception):
            extract(b"not a pdf", "https://cdn.sanity.io/files/test.pdf")

if __name__ == "__main__":
    unittest.main()
