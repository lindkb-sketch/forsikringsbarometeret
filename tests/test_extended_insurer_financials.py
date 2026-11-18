"""Source integrity for the two new insurers."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_extended_insurers import extract,update

SOURCE_TEXT='''<html><body><h1>Alm. Brand A/S - Interim report for Q3</h1>
28 October 2026. The insurance service result was DKK 755 million.
The result corresponded to a claims ratio of 59.2 and a combined ratio of 75.3.
Insurance revenue grew by 1.6% to DKK 3,054 million.
The expense ratio increased by 0.3 of a percentage point to 16.1.
</body></html>'''

class NewInsurerTests(unittest.TestCase):
    def test_official_q3_metrics_and_currency(self):
        row=extract(SOURCE_TEXT)
        self.assertEqual(row['currency'],'DKK')
        self.assertEqual(row['metrics']['insurance_revenue'],3054)
        self.assertEqual(row['metrics']['insurance_service_result'],755)
        self.assertEqual(row['metrics']['combined_ratio'],75.3)

    def test_missing_report_metric_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'expense_ratio'):
            extract(SOURCE_TEXT.replace('The expense ratio increased by 0.3 of a percentage point to 16.1.',''))

    def test_wrong_quarter_rejected(self):
        with self.assertRaisesRegex(ValueError,'reporting period'):
            extract(SOURCE_TEXT.replace('Q3','Q4'))

    def test_snapshot_noop_and_klp_not_invented(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'extended.json'
            self.assertTrue(update(SOURCE_TEXT,out))
            self.assertFalse(update(SOURCE_TEXT,out))
            import json
            data=json.loads(out.read_text())
            self.assertEqual(data['insurers']['KLP Skadeforsikring']['metrics'],{})

if __name__=='__main__':unittest.main()
