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
    def test_official_report_table_q1_q2_q3(self):
        class Page:
            def __init__(self, text): self.text = text
            def extract_text(self): return self.text
        class PDF:
            def __init__(self, q, table):
                self.pages = [Page(f"Kvartalsrapport Q{q} 2026 Fremtind Holding"),
                              Page("Innhold"),
                              Page(f"Resultatutvikling og nøkkeltall\nMNOK Q{q} 2026\n" + table),
                              Page("Noter")]
            def __enter__(self): return self
            def __exit__(self, *args): return False
        tables = {
            1: (
                "Inntekter fra forsikringstjenester 6 205 5 769 23 510 Vekst i inntekter\n"
                "Resultat fra forsikringstjenester 1 256 843 4 520\n"
                "Skadeprosent, netto etter gjenforsikring (%) 58,5 % 63,9 % 58,8 %\n"
                "Kostnadsprosent (%) 21,2 % 21,5 % 21,9 %\n"
                "Combined ratio, netto etter gjenforsikring (%) 79,8 % 85,4 % 80,8 %"),
            2: (
                "Inntekter fra forsikringstjenester 5 863 5 560 12 068 11 328 23 510 Vekst\n"
                "Resultat fra forsikringstjenester 1 321 856 2 576 1 699 4 520\n"
                "Skadeprosent, netto etter gjenforsikring (%) 54,4 % 61,6 % 56,5 % 62,7 % 58,8 %\n"
                "Kostnadsprosent (%) 23,1 % 23,0 % 22,1 % 22,3 % 21,9 %\n"
                "Combined ratio, netto etter gjenforsikring (%) 77,5 % 84,6 % 78,7 % 85,0 % 80,8 %"),
            3: (
                "Inntekter fra forsikringstjenester 6 305 6 047 18 373 17 376 23 510 sammenlignet\n"
                "Netto resultat fra gjenforsikringskontrakter -46 -56 -227 -177 81 Skadeprosent, netto etter gjenforsikring (%) 52,5 % 55,2 % 55,1 % 60,1 % 58,8 %\n"
                "Resultat fra forsikringstjenester 1 704 1 411 4 280 3 111 4 520 Kostnadsprosent (%) 20,5 % 21,4 % 21,6 % 22,0 % 21,9 %\n"
                "Combined ratio, netto etter gjenforsikring (%) 73,0 % 76,7 % 76,7 % 82,1 % 80,8 %"),
        }
        expected = {1: (6205, None), 2: (5863, 12068), 3: (6305, 18373)}
        for q, (quarter, ytd) in expected.items():
            with self.subTest(q=q), patch("import_fremtind_holding.pdfplumber.open", return_value=PDF(q, tables[q])):
                rows = extract(b"%PDF-test", "https://cdn.sanity.io/files/report.pdf")
                values = {(r["period_type"], r["metric"]): r["value"] for r in rows if r["year"] == 2026}
                comparisons = {(r["period_type"],r["metric"]):r["value"] for r in rows if r["year"] == 2025}
                self.assertEqual(comparisons[("quarter","insurance_revenue")],{1:5769,2:5560,3:6047}[q])
                self.assertEqual(comparisons[("quarter","combined_ratio")],{1:85.4,2:84.6,3:76.7}[q])
                if q > 1:
                    self.assertEqual(comparisons[("ytd","insurance_revenue")],{2:11328,3:17376}[q])
                    self.assertEqual(comparisons[("ytd","combined_ratio")],{2:85.0,3:82.1}[q])
                self.assertEqual(values[("quarter", "insurance_revenue")], quarter)
                self.assertEqual(values[("quarter", "combined_ratio")], {1:79.8,2:77.5,3:73.0}[q])
                if ytd is not None:
                    self.assertEqual(values[("ytd", "insurance_revenue")], ytd)
                    self.assertEqual(len(rows), 20)
                else:
                    self.assertEqual(len(rows), 10)
    def test_non_pdf_rejected(self):
        with self.assertRaises(Exception):
            extract(b"not a pdf", "https://cdn.sanity.io/files/test.pdf")

if __name__ == "__main__":
    unittest.main()
