import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SolvencyRolloverTests(unittest.TestCase):
 def test_importer_checks_same_quarter_last_year(self):
  s=(ROOT/'scripts/import_group_solvency_pdf.py').read_text()
  self.assertIn('for target_year in (year-1,year):',s)
  self.assertIn("'metric')=='solvency_ratio'",s)
  self.assertIn("source_page=page",s)
 def test_dashboard_uses_matching_year_prior(self):
  s=(ROOT/'scripts/quarterly_runtime.js').read_text()
  self.assertIn("quote(name,type,year-1,quarter,metric)",s)
  self.assertIn("data[k+'Prev']=fmt(prior.value",s)
  self.assertIn("if(metric==='solvency_ratio')",s)
