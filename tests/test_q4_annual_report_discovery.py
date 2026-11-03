"""Q4 reports and annual reports must supply an explicit isolated quarter."""
import unittest
import subprocess
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
 def test_q4_guard_is_executable_not_hidden_inside_comment(self):
  runtime=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
  fn='  function addQuarter('+runtime.split('  function addQuarter(',1)[1].split('  function addYtd(',1)[0]
  self.assertNotIn(r'\n',fn)
  js=r"""
  const feed = new Map([
    ['2026:3:insurance_revenue', {value:300,unit:'NOKm',scope:'group'}],
    ['2026:4:insurance_revenue', {value:420,unit:'NOKm',scope:'group'}],
    ['2026:1:insurance_service_result', {value:50,unit:'NOKm',scope:'group'}],
    ['2026:2:insurance_service_result', {value:90,unit:'NOKm',scope:'group'}],
  ]);
  const lookup=(company,type,year,quarter,metric)=>
    type==='ytd'?feed.get(year+':'+quarter+':'+metric):null;
  const isSameBasis=(a,b)=>a.unit===b.unit&&a.scope===b.scope;
  """+fn+r"""
  const assert=(condition,msg)=>{if(!condition)throw Error(msg)};
  assert(addQuarter('Frende',2026,4,'insurance_revenue')===null,
    'Q4 premium must not derive 420-300');
  assert(addQuarter('Frende',2026,4,'combined_ratio')===null,
    'Q4 ratio must not be inferred from YTD');
  const q2=addQuarter('Frende',2026,2,'insurance_service_result');
  assert(q2?.value===40&&q2.derived_quarter===true,
    'Q2 additive YTD fallback must remain available');
  assert(addQuarter('Frende',2026,2,'combined_ratio')===null,
    'Only additive metric fallback is allowed');
  console.log('Q4_EXECUTABLE_GUARD_PASS');
  """
  result=subprocess.run(['node','-e',js],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertIn('Q4_EXECUTABLE_GUARD_PASS',result.stdout)

 def test_four_slot_rollover_preserves_december(self):
  from scripts.audit_profitability_history import window
  self.assertEqual(window(2027,1),[(2026,1),(2026,2),(2026,3),(2026,4),(2027,1)])
  self.assertEqual(window(2027,2),[(2026,2),(2026,3),(2026,4),(2027,1),(2027,2)])

if __name__=='__main__':
 unittest.main()
