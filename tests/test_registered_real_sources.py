import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from publish_geographic_workbooks import prepare
class RegisteredSources(unittest.TestCase):
 def test_tryg_q2_official_exact_urls(self):
  registry=json.loads((ROOT/'data/geographic_workbooks.json').read_text())
  rows=[x for x in registry['workbooks'] if x['company']=='Tryg' and x['year']==2026 and x['quarter']==2]
  self.assertEqual(len(rows),1)
  self.assertTrue(rows[0]['workbook_url'].startswith('https://tryg.com/system/files/2026-07/'))
  self.assertTrue(rows[0]['report_pdf_url'].endswith('.pdf'))
 def test_invalid_download_does_not_mutate_existing_observations(self):
  registry=json.loads((ROOT/'data/geographic_workbooks.json').read_text())
  existing=json.loads((ROOT/'data/financial_observations.json').read_text())
  snapshot=json.dumps(existing,sort_keys=True)
  with self.assertRaises(Exception):prepare(registry,existing,fetcher=lambda url:b'not-an-xlsx')
  self.assertEqual(json.dumps(existing,sort_keys=True),snapshot)
 def test_workflow_fallback_and_feed(self):
  workflow=(ROOT/'.github/workflows/update.yml').read_text()
  self.assertNotIn('continue-on-error: true',workflow)
  self.assertIn('python scripts/run_pipeline.py',workflow)
  self.assertIn('quarterly_editorial.json',workflow)
