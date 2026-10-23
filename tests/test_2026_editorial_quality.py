"""Quality gate for published historical 2026 briefs and future quarter updates."""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class EditorialQuality2026(unittest.TestCase):
 def test_existing_2026_reports_have_concise_nonverbatim_brief(self):
  data=json.loads((ROOT/'data/quarterly_editorial.json').read_text())
  for quarter in ('Q1 2026','Q2 2026','Q3 2026'):
   with self.subTest(quarter=quarter):
    items=data['periods'][quarter]['brief']
    self.assertGreater(len(items),0)
    self.assertLessEqual(len(items),4)
    self.assertLessEqual(sum(len(x['text'].split()) for x in items),220)
    for item in items:
     self.assertEqual(item['type'],'qualitative_quarter_theme')
     self.assertNotIn('omtaler i kvartalsrapporten:',item['text'])
     self.assertNotEqual(item.get('basis'),'issuer_pdf_verbatim')
     self.assertTrue(item['source_url'].startswith('https://'))
 def test_future_refresh_and_publishing_guardrails_exist(self):
  refresh=(ROOT/'scripts/refresh_report_commentary.py').read_text()
  pipeline=(ROOT/'scripts/run_pipeline.py').read_text()
  check=(ROOT/'scripts/check_quarterly_brief.py').read_text()
  self.assertIn("if x['year']<2026:continue",refresh)
  self.assertIn("refresh_report_commentary.py",pipeline)
  self.assertIn("Raw PDF quote",check)
if __name__=='__main__':unittest.main()
