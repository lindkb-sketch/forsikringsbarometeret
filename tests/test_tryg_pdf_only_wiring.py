import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PdfOnly(unittest.TestCase):
    def test_pipeline(self):
        code=(ROOT/'scripts/run_pipeline.py').read_text()
        self.assertNotIn("'publish_geographic_workbooks.py'",code)
    def test_tryg_import(self):
        code=(ROOT/'scripts/import_tryg.py').read_text()
        self.assertNotIn('prepare(wb',code)
        self.assertNotIn('workbook_url',code)
    def test_discovery(self):
        code=(ROOT/'scripts/discover_tryg.py').read_text()
        self.assertNotIn('workbook_url',code)
if __name__=='__main__':unittest.main()
