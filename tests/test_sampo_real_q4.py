#!/usr/bin/env python3
"""Real issuer Q4 2025 regression. Never publishes historical test data."""
import sys,unittest,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sampo_publish import parse
URL='https://www.sampo.com/globalassets/investors/quarterly-reporting/2025/q4/financial-statement-release-2025.pdf'
class TestRealIssuerQ4(unittest.TestCase):
 def test_real_q4_2025(self):
  req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=60) as resp:pdf=resp.read(30_000_001)
  self.assertLessEqual(len(pdf),30_000_000)
  rows=parse(pdf,URL,2025,4)
  self.assertEqual(len(rows),15)
  by={(r['segment'],r['metric']):r for r in rows}
  self.assertEqual(by[(None,'insurance_revenue')]['value'],2322)
  self.assertEqual(by[(None,'insurance_service_result')]['value'],364)
  self.assertAlmostEqual(by[(None,'combined_ratio')]['value'],84.3)
  self.assertEqual(by[('Private Nordic','insurance_service_result')]['value'],183)
  self.assertEqual(by[('Nordic Commercial','insurance_service_result')]['value'],96)
  self.assertTrue(all(r['quarter']==4 and r['year']==2025 and r['source_page']>0 for r in rows))
if __name__=='__main__':unittest.main()
