import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from watch_reports import verify_pdf,scan
class WatchReportsTests(unittest.TestCase):
 def test_valid_pdf_signature(self):self.assertTrue(verify_pdf(b"%PDF-1.7"+b"x"*1200))
 def test_reject_html(self):self.assertFalse(verify_pdf(b"<html>"+b"x"*1200))
 def test_reject_truncated(self):self.assertFalse(verify_pdf(b"%PDF-1.7"))
 def test_monitor_without_network(self):
  r=scan(fetcher=lambda url:b"%PDF-1.7"+b"x"*1200)
  self.assertTrue(r["all_sources_reachable"])
  self.assertEqual(len(r["reports"]),1)
if __name__=="__main__":unittest.main()
