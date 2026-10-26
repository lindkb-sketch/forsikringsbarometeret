"""Regression checks for automatic issuer-linked Gjensidige Q3 discovery."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_gjensidige_latest import import_period, periods_due, import_due

class GjensidigeLatestTests(unittest.TestCase):
    def test_future_years_are_discovered_without_hardcoded_quarter(self):
        self.assertEqual(periods_due(date(2026,10,23)),[(y,q) for y in (2024,2025,2026) for q in range(1,5) if (y,q)<(2026,4)])
        self.assertEqual(periods_due(date(2027,1,7)),[(y,q) for y in (2024,2025,2026) for q in range(1,5)])
        self.assertEqual(periods_due(date(2027,4,2))[-1],(2027,1))
        self.assertEqual(periods_due(date(2028,1,2))[-1],(2027,4))

    def test_auto_scan_checks_every_due_quarter_and_does_not_fabricate(self):
        calls=[]
        def fake_import(year,quarter):
            calls.append((year,quarter))
            return {'status':'not_discovered','period':f'Q{quarter} {year}','imported':0}
        result=import_due(date(2027,4,1),fake_import)
        self.assertEqual(calls,periods_due(date(2027,4,1)))
        self.assertTrue(all(x['imported']==0 for x in result))

    def test_absent_report_does_not_modify_data(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "observations.json"
            target.write_text('{"observations": []}')
            result = import_period(2026, 3, fetch_index=lambda url: "<html>Not published</html>", target=target)
            self.assertEqual(result["status"], "not_discovered")
            self.assertEqual(target.read_text(), '{"observations": []}')

    def test_approved_historical_pdf_is_still_validated_before_backfill(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "observations.json"
            target.write_text('{"observations": []}')
            result = import_period(2026, 2, fetch_index=lambda url: "<html>No Q2 link</html>",
                                   fetch_pdf=lambda url: b"not a pdf", target=target)
            self.assertEqual(result["status"], "import_failed")
            self.assertIn("mb.cision.com",result["source"])
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
