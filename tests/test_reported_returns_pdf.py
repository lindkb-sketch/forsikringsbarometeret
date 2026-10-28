import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_reported_returns import extract

class Page:
    def __init__(self,text):self.text=text
    def extract_text(self):return self.text
class PDF:
    def __init__(self,text):self.pages=[Page(text)]
    def __enter__(self):return self
    def __exit__(self,*args):return False

class ReportedReturnTests(unittest.TestCase):
    def extract_text(self,company,text):
        with patch('import_reported_returns.pdfplumber.open',return_value=PDF(text)):
            return extract(b'%PDF-example',company,2026,3)
    def test_tryg_roof_not_roe(self):
        page,value,label=self.extract_text('Tryg','The return on own funds (ROOF) was 47.0%.')
        self.assertEqual((page,value,label),(1,47.0,'ROOF annualised'))
    def test_protector_annualised_roe(self):
        page,value,label=self.extract_text('Protector','Return on equity, annualised 47.9 %')
        self.assertEqual((value,label),(47.9,'ROE annualised'))
    def test_gjensidige_annualised_roe(self):
        _,value,_=self.extract_text('Gjensidige','The annualised return on equity was 34.2 per cent.')
        self.assertEqual(value,34.2)
    def test_protector_issuer_quarterly_table_with_footnote(self):
        text="Quarterly outline Q3 2026 Q3 2025 Q1-Q3 2026\\nReturn on equity, annualised¹ % 47.9 % 28.7 % 33.8 %"
        page,value,label=self.extract_text('Protector',text)
        self.assertEqual((page,value,label),(1,47.9,'ROE annualised'))
    def test_ambiguous_values_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            self.extract_text('Tryg','ROOF was 47.0 %. ROOF was 40.0 %.')
    def test_no_equity_metric_from_investment_returns(self):
        with self.assertRaises(ValueError):
            self.extract_text('Protector','Return on investments 7.6 %')
    def test_scheduled_import_and_chart_binding(self):
        root=Path(__file__).resolve().parents[1]
        pipeline=(root/'scripts/run_pipeline.py').read_text()
        runtime=(root/'scripts/quarterly_runtime.js').read_text()
        self.assertIn("'import_reported_returns.py'",pipeline)
        self.assertIn("profitabilityReturns[name][l]",runtime)
        self.assertIn("return_on_equity:'return'",runtime)

if __name__=='__main__':unittest.main()
