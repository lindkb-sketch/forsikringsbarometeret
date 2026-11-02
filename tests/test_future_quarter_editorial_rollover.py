"""Future-quarter rollover: never copy Q3 prose or invent issuer events."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_editorial import build

class FutureQuarterEditorial(unittest.TestCase):
 def test_new_quarter_generates_automatic_source_backed_copy(self):
  base=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  rows=base['observations']
  company='Protector'
  latest=[r for r in rows if r.get('company')==company and r.get('year')==2026
          and r.get('quarter')==3 and r.get('scope')=='group'
          and r.get('period_type')=='quarter'
          and r.get('metric') in ('combined_ratio','insurance_revenue','insurance_service_result')]
  self.assertGreaterEqual(len(latest),2)
  fake=copy.deepcopy(base)
  for row in latest:
   next_row=copy.deepcopy(row)
   next_row.update(year=2026,quarter=4,source_url='https://example.org/issuer-q4-2026.pdf')
   fake['observations'].append(next_row)
  result=build(fake,{'items':[]})
  item=result['periods']['Q4 2026']['by_company'][company]
  self.assertEqual(item['period'],'Q4 2026')
  self.assertTrue(item['reader_summary'])
  self.assertEqual(item['source_url'],'https://example.org/issuer-q4-2026.pdf')
  self.assertNotIn('editorial_review',item)
  self.assertFalse(item.get('qualitative_notes'))
  self.assertNotIn('Knif',item['reader_summary'])
  self.assertNotIn('XPENG',item['reader_summary'])
 def test_no_new_source_means_no_new_quarter(self):
  feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  result=build(feed,{'items':[]})
  self.assertNotIn('Q4 2026',result['periods'])
