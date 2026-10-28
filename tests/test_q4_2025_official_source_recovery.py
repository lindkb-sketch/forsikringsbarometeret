"""Regression tests for official 2025 Q4 sources without year-specific future limits."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class OfficialQ4ImportTests(unittest.TestCase):
 def test_gjensidige_official_q4_document_is_registered(self):
  from scripts.gjensidige_publish import APPROVED_PDFS
  self.assertIn((2025,4),APPROVED_PDFS)
  self.assertTrue(APPROVED_PDFS[(2025,4)].startswith('https://live.euronext.com/'))
 def test_gjensidige_import_checks_every_completed_quarter(self):
  from scripts.import_gjensidige_latest import periods_due
  from datetime import date
  self.assertIn((2025,4),periods_due(date(2026,10,26)))
  self.assertIn((2026,4),periods_due(date(2027,1,15)))
 def test_protector_attempts_q4_in_verified_pipeline(self):
  s=(ROOT/'scripts/protector_publish.py').read_text()
  self.assertIn('relevant={(y,q) for scope,y,q,metric in values if y>=2025}',s)
  self.assertIn('for year,quarter in sorted(relevant):',s)
  self.assertIn('pages=parse_pdf(blob,year,quarter)',s)
  self.assertIn('page_no=provenance(pages,scope,metric,value)',s)
if __name__=='__main__':unittest.main()
