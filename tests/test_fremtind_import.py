import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_fremtind_holding import number, extract

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
    def test_non_pdf_rejected(self):
        with self.assertRaises(Exception):
            extract(b"not a pdf", "https://cdn.sanity.io/files/test.pdf")

if __name__ == "__main__":
    unittest.main()
