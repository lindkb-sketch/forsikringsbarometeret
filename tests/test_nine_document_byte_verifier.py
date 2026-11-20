import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_nine_document_bytes import approved, period_matches, verify_pdf, download
from discover_reports import discover

class NineDocumentVerifierTests(unittest.TestCase):
 def test_authorized_cdn(self):
  self.assertTrue(approved('Fremtind','https://cdn.sanity.io/files/a.pdf'))
  self.assertTrue(approved('Alm. Brand','https://s29.q4cdn.com/228553818/files/a.pdf'))
 def test_reject_domain_spoof_and_http(self):
  self.assertFalse(approved('Fremtind','https://cdn.sanity.io.evil.test/a.pdf'))
  self.assertFalse(approved('Tryg','http://tryg.com/report.pdf'))
  self.assertFalse(approved('Tryg','https://tryg.com.evil.test/report.pdf'))
 def test_period_matching(self):
  self.assertTrue(period_matches('Q3 2026',2026,3))
  self.assertTrue(period_matches('3. kvartal 2026',2026,3))
  self.assertTrue(period_matches('2026-Q3',2026,3))
  self.assertFalse(period_matches('Q2 2026',2026,3))
 def test_pdf_bytes_mandatory(self):
  with self.assertRaises(ValueError):verify_pdf(b'not a pdf','Tryg','https://tryg.com/Q3.pdf',2026,3)
 def test_cross_domain_redirect_rejected(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def geturl(self):return 'https://evil.test/report.pdf'
   def read(self,n):return b'%PDF-1.7'
  with self.assertRaisesRegex(ValueError,'redirect'):
   download('Tryg','https://tryg.com/q3-report.pdf',opener=lambda *a,**k:Response())
 def test_issuer_cdn_presentation_discovered(self):
  html='<a href="https://s29.q4cdn.com/228553818/files/q3-2026-results-presentation.pdf">Q3 2026 presentation</a>'
  x=discover(html,'https://investorrelations.almbrand.dk/English/financials/default.aspx','Alm. Brand')
  self.assertEqual(len(x),1)
  self.assertEqual(x[0]['document_type'],'results_presentation')
 def test_legacy_xlsx_discovery_retained(self):
  html='<a href="/q3-interim-report.xlsx">Q3 2026 interim report</a>'
  self.assertEqual(len(discover(html,'https://tryg.com/en/downloads-2026','Tryg')),1)
 def test_unapproved_external_presentation_rejected(self):
  html='<a href="https://random-cdn.test/q3-2026-presentation.pdf">Q3 2026 presentation</a>'
  self.assertEqual(discover(html,'https://tryg.com/en/downloads-2026','Tryg'),[])
if __name__=='__main__':unittest.main()
