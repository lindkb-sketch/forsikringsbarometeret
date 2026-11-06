import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_group_solvency_pdf import extract
class SolvencyHistoryTests(unittest.TestCase):
 def test_all_quarters_and_prior_year_are_attempted(self):
  src=(ROOT/'scripts/import_group_solvency_pdf.py').read_text()
  self.assertIn("'Gjensidige'",src)
  self.assertIn("r['year']>=2025",src)
  self.assertIn("r['year']==2026",src)
  self.assertIn("source_page=page",src)
 def test_dashboard_same_quarter_prior_year(self):
  js=(ROOT/'scripts/quarterly_runtime.js').read_text()
  self.assertIn("quote(name,type,year-1,quarter,metric)",js)
  self.assertIn("if(metric==='solvency_ratio')",js)
