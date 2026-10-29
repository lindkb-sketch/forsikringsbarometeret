import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_reported_returns import extract, official_tryg_presentations

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
    def test_fremtind_adjusted_return_wrapped_pdf_table(self):
        sample=("Fremtind Holding Q3 2026\\n"
            "Annualisert egenkapitalavkastning justert for\\n"
            "transaksjonen med EikaForsikring AS 32,2 % 34,2 %")
        _,value,definition=self.extract_text('Fremtind',sample)
        self.assertEqual(value,32.2)
        self.assertIn('Eika',definition)
    def test_tryg_roof_wrapped_under_solveny_header(self):
        sample=("Dividend and solvency\\n"
            "The return on own funds (ROOF)\\nwas 47.0%.")
        _,value,definition=self.extract_text('Tryg',sample)
        self.assertEqual(value,47.0)
        self.assertEqual(definition,'ROOF annualised')
    def test_protector_annualised_roe(self):
        page,value,label=self.extract_text('Protector','Return on equity, annualised 47.9 %')
        self.assertEqual((value,label),(47.9,'ROE annualised'))
    def test_gjensidige_annualised_roe(self):
        _,value,_=self.extract_text('Gjensidige','The annualised return on equity was 34.2 per cent.')
        self.assertEqual(value,34.2)
    def test_protector_issuer_quarterly_table_with_footnote(self):
        text="Quarterly outline Q3 2026 Q3 2025 Q1-Q3 2026\nReturn on equity, annualised¹ % 47.9 % 28.7 % 33.8 %"
        page,value,label=self.extract_text('Protector',text)
        self.assertEqual((page,value,label),(1,47.9,'ROE annualised'))
    def test_ambiguous_values_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            self.extract_text('Tryg','ROOF was 47.0 %. ROOF was 40.0 %.')
    def test_no_equity_metric_from_investment_returns(self):
        with self.assertRaises(ValueError):
            self.extract_text('Protector','Return on investments 7.6 %')
    def test_official_tryg_quarter_presentation_discovery(self):
        from unittest.mock import MagicMock
        html=(b'<a href="/sites/tryg.com/files/2026-01/Q4%202025%20-%20Investor%20presentation.pdf">'
              b'Q4 2025 - Investor presentation.pdf</a>'
              b'<a href="/tables/Q4-2025.xlsx">Q4 2025 - Investor tables.xlsx</a>')
        mock=MagicMock()
        mock.__enter__.return_value.read.return_value=html
        with patch('urllib.request.urlopen',return_value=mock):
            urls=list(official_tryg_presentations(2025,4))
        self.assertEqual(len(urls),1)
        self.assertTrue(urls[0].endswith('.pdf'))
    def test_presentation_discovery_does_not_accept_unrelated_quarters(self):
        from unittest.mock import MagicMock
        html=(b'<a href="/Q3_2025_Investor_presentation.pdf">Q3 2025 - Investor presentation.pdf</a>')
        mock=MagicMock()
        mock.__enter__.return_value.read.return_value=html
        with patch('urllib.request.urlopen',return_value=mock):
            self.assertEqual(list(official_tryg_presentations(2025,4)),[])
    def test_scheduled_import_and_chart_binding(self):
        root=Path(__file__).resolve().parents[1]
        pipeline=(root/'scripts/run_pipeline.py').read_text()
        runtime=(root/'scripts/quarterly_runtime.js').read_text()
        self.assertIn("'import_reported_returns.py'",pipeline)
        self.assertIn("profitabilityReturns[name][l]",runtime)
        self.assertIn("return_on_equity:'return'",runtime)

if __name__=='__main__':unittest.main()
