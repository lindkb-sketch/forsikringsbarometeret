"""Q4 reports and annual reports must supply an explicit isolated quarter."""
import unittest
from pathlib import Path
from scripts.discover_reports import discover

ROOT=Path(__file__).resolve().parents[1]

class Q4AnnualDiscoveryTests(unittest.TestCase):
 def test_annual_results_are_discoverable_without_approving_numbers(self):
  url='https://issuer.example.com/investors/'
  links=(
    '<a href="reports/annual-report-2026.pdf">Annual Report 2026</a>'
    '<a href="reports/financial-statements-release-2026.pdf">Financial Statements Release 2026</a>'
    '<a href="reports/q4-2026-report.pdf">Q4 2026 report</a>'
    '<a href="reports/årsrapport-2026.pdf">Årsrapport 2026</a>'
    '<a href="reports/investor-presentation-2026.pdf">Investor presentation</a>'
  )
  found=discover(links,url,'Tryg')
  self.assertEqual(len(found),4)
  self.assertTrue(all(x['status']=='candidate_requires_quarterly_report_verification' for x in found))
 def test_no_q4_ytd_difference_fallback(self):
  runtime=(ROOT/'scripts/quarterly_runtime.js').read_text()
  fn=runtime.split('  function addQuarter(',1)[1].split('  function addYtd(',1)[0]
  self.assertIn('if(quarter===4)return null;',fn)
 def test_four_slot_rollover_preserves_december(self):
  from scripts.audit_profitability_history import window
  self.assertEqual(window(2027,1),[(2026,1),(2026,2),(2026,3),(2026,4),(2027,1)])
  self.assertEqual(window(2027,2),[(2026,2),(2026,3),(2026,4),(2027,1),(2027,2)])

if __name__=='__main__':
 unittest.main()
