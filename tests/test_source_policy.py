import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from source_policy import validate_source_policy
class SourcePolicyTest(unittest.TestCase):
 def test_reject_pdf_norway_without_named_geography(self):
  self.assertTrue(validate_source_policy([dict(company='Gjensidige',scope='norway',source_type='official_quarterly_report')]))
  self.assertTrue(validate_source_policy([dict(company='Tryg',scope='norway',source_type='official_quarterly_report')]))
 def test_accept_verified_excel_norway(self):
  row=dict(company='Gjensidige',scope='norway',source_type='official_investor_tables',
    source_url='https://issuer.example/figures.xlsx',source_sheet='Norway',
    source_cell='B12',source_document_url='https://issuer.example/report.pdf',source_sha256='a'*64)
  self.assertFalse(validate_source_policy([row]))
  self.assertTrue(validate_source_policy([{**row,'source_cell':None}]))
 def test_accept_explicit_tryg_norway_geography_pdf(self):
  row=dict(company='Tryg',scope='norway',source_type='official_quarterly_report',
    source_url='https://issuer.example/report.pdf',source_page=36,
    source_section='Quarterly outline - Geography / Norwegian general insurance',source_document_period='Q3 2026')
  self.assertFalse(validate_source_policy([row]))
  self.assertTrue(validate_source_policy([{**row,'source_section':'Group summary'}]))
if __name__=='__main__':unittest.main()
