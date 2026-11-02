import json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from source_policy import validate_source_policy
from discover_tryg import parse as discover_tryg_pdf

class RegisteredSources(unittest.TestCase):
 def test_tryg_registered_candidates_are_pdf_only(self):
  markup=('''<a href="https://tryg.com/system/files/2026-10/Interim%20report%20Q3%202026.pdf">Interim report Q3 2026</a>'''
          '<a href="https://tryg.com/system/files/2026-10/Investor%20tables%20Q3%202026.xlsx">Investor tables Q3 2026</a>')
  candidates=discover_tryg_pdf(markup,2026)
  self.assertTrue(candidates)
  for item in candidates:
   self.assertTrue(item['report_pdf_url'].lower().split('?')[0].endswith('.pdf'))
   self.assertFalse(any(key in item for key in ('workbook_url','xlsx_url','excel_url')))

 def test_excel_provenance_is_rejected(self):
  observation=dict(company='Tryg',scope='norway',source_type='official_investor_tables',
    source_url='https://tryg.com/figures.xlsx')
  self.assertTrue(validate_source_policy([observation]))

 def test_workflow_fallback_and_feed(self):
  workflow=(ROOT/'.github/workflows/update.yml').read_text()
  self.assertNotIn('continue-on-error: true',workflow)
  self.assertIn('python scripts/run_pipeline.py',workflow)
  self.assertIn('quarterly_editorial.json',workflow)
if __name__=='__main__':unittest.main()
