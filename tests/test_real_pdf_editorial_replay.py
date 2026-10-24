"""Replay previously extracted official PDF evidence without touching production data."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from synthesize_report_commentary import synthesize
class OfficialArchiveReplay(unittest.TestCase):
 def test_real_extracted_issuer_evidence_is_safe_to_summarize(self):
  archive=json.loads((ROOT/'data/quarterly_insights.json').read_text())
  rows=[x for label,items in archive['periods'].items() if label.endswith('2026')
        for x in items if x.get('basis')=='issuer_pdf_verbatim']
  self.assertGreater(len(rows),0)
  selected=[synthesize(x) for x in rows]
  publishable=[x for x in selected if x]
  self.assertGreaterEqual(len(publishable),1,'No actual official extracted passages pass rules')
  for item in publishable:
   self.assertIn('source_excerpt',item)
   self.assertNotIn('omtaler i kvartalsrapporten',item['text'])
   self.assertTrue(item['sources'][0]['page']>=1)
   self.assertEqual(len(item['sources'][0]['sha256']),64)
   self.assertLessEqual(len(item['text'].split()),45)
  print('ARCHIVE_PDF_EDITORIAL_REPLAY',len(rows),'candidates;',len(publishable),'conservatively publishable')
if __name__=='__main__':unittest.main()
