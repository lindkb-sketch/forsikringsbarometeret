#!/usr/bin/env python3
"""Real Q3 2026 Sampo issuer PDF, compared with independently published key figures."""
import sys,unittest,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sampo_publish import parse
URL='https://www.sampo.com/globalassets/investors/quarterly-reporting/2026/q3/interim-statement_q3_2026.pdf'
class SampoQ32026SourceTests(unittest.TestCase):
 def test_official_q3_2026_numbers(self):
  req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=60) as response:pdf=response.read(30_000_001)
  self.assertLessEqual(len(pdf),30_000_000)
  rows=parse(pdf,URL,2026,3)
  self.assertEqual(len(rows),15)
  group={r['metric']:r for r in rows if r['scope']=='group'}
  expected={'insurance_revenue':2503,'insurance_service_result':435,'loss_ratio':57.7,'expense_ratio':24.9,'combined_ratio':82.6}
  for metric,value in expected.items():
   with self.subTest(metric=metric):self.assertAlmostEqual(group[metric]['value'],value)
  self.assertTrue(all(r['source_page']>0 and len(r['source_sha256'])==64 for r in rows))
if __name__=='__main__':unittest.main()
