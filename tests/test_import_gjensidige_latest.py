"""Regression checks for automatic issuer-linked Gjensidige Q3 discovery."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_gjensidige_latest import import_period

class GjensidigeLatestTests(unittest.TestCase):
    def test_absent_report_does_not_modify_data(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "observations.json"
            target.write_text('{"observations": []}')
            result = import_period(2026, 3, fetch_index=lambda url: "<html>Not published</html>", target=target)
            self.assertEqual(result["status"], "not_discovered")
            self.assertEqual(target.read_text(), '{"observations": []}')

    def test_issuer_link_without_valid_pdf_cannot_publish(self):
        markup = '<a href="https://mb.cision.com/Main/123/456/789.pdf">23 October 2026 Interim report Q3 2026 (PDF)</a>'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "observations.json"
            target.write_text('{"observations": []}')
            result = import_period(2026, 3, fetch_index=lambda url: markup,
                                   fetch_pdf=lambda url: b"not a pdf", target=target)
            self.assertEqual(result["status"], "import_failed")
            self.assertEqual(target.read_text(), '{"observations": []}')

if __name__ == "__main__":
    unittest.main()
