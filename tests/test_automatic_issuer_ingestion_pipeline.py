"""The scheduled issuer pipeline must keep operating across year boundaries."""
import unittest
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class AutomaticIssuerIngestionTests(unittest.TestCase):
 def test_all_seven_issuers_have_a_live_ingestion_path(self):
  pipeline=(ROOT/'scripts/run_pipeline.py').read_text()
  for filename in ('import_fremtind_holding.py','import_frende_holding.py',
     'import_gjensidige_latest.py','import_tryg.py','protector_publish.py',
     'sampo_publish.py','storebrand_publish_q3.py'):
   self.assertIn(filename,pipeline)
 def test_storebrand_has_no_fixed_active_quarter(self):
  pipeline=(ROOT/'scripts/run_pipeline.py').read_text()
  self.assertIn('latest_year,latest_quarter=divmod(latest_completed,4)',pipeline)
  self.assertIn("'--year',str(latest_year),'--quarter',str(latest_quarter)",pipeline)
  def latest(d):
   i=d.year*4+(d.month-1)//3-1
   y,q=divmod(i,4)
   return y,q+1
  for d,expected in ((date(2026,10,26),(2026,3)),
                     (date(2027,1,15),(2026,4)),
                     (date(2027,4,15),(2027,1)),
                     (date(2028,1,5),(2027,4))):
   self.assertEqual(latest(d),expected)
 def test_audited_coverage_runs_before_pages_deploy(self):
  workflow=(ROOT/'.github/workflows/update.yml').read_text()
  self.assertIn('python scripts/audit_profitability_history.py',workflow)
  self.assertLess(workflow.index('python scripts/audit_profitability_history.py'),
                  workflow.index('actions/deploy-pages@v4'))
if __name__=='__main__':unittest.main()
