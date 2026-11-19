import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from discover_reports import discover,scan
BASE="https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa"
class DiscoveryTests(unittest.TestCase):
 def test_official_report(self):
  h='<a href="/q2-interim-report.pdf">Interim report Q2 2026</a>'
  self.assertEqual(len(discover(h,BASE,"Storebrand")),1)
 def test_press_release_not_report(self):
  h='<a href="/q2-press-release.pdf">Q2 report press release</a>'
  self.assertEqual(discover(h,BASE,"Storebrand"),[])
 def test_presentation_discovered_separately(self):
  h='<a href="/q2-report-presentation.pdf">Q2 report presentation</a>'
  found=discover(h,BASE,"Storebrand")
  self.assertEqual(len(found),1)
  self.assertEqual(found[0]["document_type"],"results_presentation")
  self.assertIn("candidate",found[0]["status"])
 def test_generic_presentation_not_assigned_to_quarter(self):
  self.assertEqual(discover('<a href="/investor-presentation.pdf">Investor presentation</a>',BASE,"Storebrand"),[])
 def test_report_and_presentation_distinct(self):
  h='<a href="/q2-interim-report.pdf">Q2 report</a><a href="/q2-results-presentation.pdf">Q2 presentation</a>'
  self.assertEqual({r["document_type"] for r in discover(h,BASE,"Storebrand")},{"quarterly_report","results_presentation"})
 def test_external_not_accepted(self):
  h='<a href="https://example.org/q2-interim-report.pdf">Q2 report</a>'
  self.assertEqual(discover(h,BASE,"Storebrand"),[])
 def test_no_automatic_approval(self):
  h='<a href="/q2-interim-report.pdf">Interim report Q2 2026</a>'
  self.assertIn("candidate",discover(h,BASE,"Storebrand")[0]["status"])
 def test_scan_without_network(self):
  result=scan(fetcher=lambda url:'<a href="/q2-interim-report.pdf">Interim report Q2 2026</a>')
  self.assertTrue(result["complete"])
if __name__=="__main__":unittest.main()
