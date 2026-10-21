import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from source_policy import validate_source_policy
class SourcePolicyTest(unittest.TestCase):
 def test_reject_pdf_norway(self):
  self.assertTrue(validate_source_policy([dict(company='Gjensidige',scope='norway',source_type='official_quarterly_report')]))
 def test_accept_excel_norway(self):
  self.assertFalse(validate_source_policy([dict(company='Tryg',scope='norway',source_type='official_investor_workbook')]))
