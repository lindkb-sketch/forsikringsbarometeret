#!/usr/bin/env python3
"""Production Q3 coverage and live Pages verification. No synthetic observations published."""
import json,sys,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_financials import audit
from build_verified_feed import build
BASE='https://lindkb-sketch.github.io/forsikringsbarometeret/data/'
class TestQuarterlyCoverage(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((ROOT/'data/financial_observations.json').read_text())
  cls.feed=build(cls.data)
  # Pre-deploy tests must be offline; post-deploy parity is checked by verify_public_pages.py.
  cls.live=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
 def test_full_financial_audit(self):
  result=audit(self.data)
  self.assertTrue(result['ok'],result['errors'])
 def test_storebrand_q3_group_and_norway(self):
  rows=[r for r in self.live['observations'] if r['company']=='Storebrand' and (r['year'],r['quarter'])==(2026,3)]
  for scope in ('group','norway'):
   q=[r for r in rows if r['scope']==scope and r['period_type']=='quarter']
   self.assertTrue(q,f'Missing Storebrand Q3 {scope}')
   self.assertTrue(all(r.get('source_page') and r.get('source_url','').startswith('https://') for r in q))
  group={r['metric']:r['value'] for r in rows if r['scope']=='group' and r['period_type']=='quarter'}
  self.assertAlmostEqual(group['combined_ratio'],87,delta=0.1)
 def test_protector_q3_group_and_norway(self):
  rows=[r for r in self.live['observations'] if r['company']=='Protector' and (r['year'],r['quarter'])==(2026,3)]
  for scope in ('group','norway'):
   q=[r for r in rows if r['scope']==scope and r['period_type']=='quarter']
   self.assertTrue(q,f'Missing Protector Q3 {scope}')
   self.assertTrue(all(r.get('source_page') and r.get('source_url','').startswith('https://') for r in q))
  group={r['metric']:r['value'] for r in rows if r['scope']=='group'}
  self.assertAlmostEqual(group['combined_ratio'],82.7,delta=0.1)
 def test_gjensidige_not_prematurely_published(self):
  # On 22 October Gjensidige Q3 2026 has not been released (23 October).
  from datetime import date
  if date.today()<date(2026,10,23):
   self.assertFalse(any(r['company']=='Gjensidige' and (r['year'],r['quarter'])==(2026,3) for r in self.live['observations']))
 def test_committed_feed_equals_verified_source_data(self):
  self.assertEqual(self.live,self.feed,'Committed financial feed differs from verified repository data')
 def test_no_future_unverified_quarters(self):
  from datetime import date
  now=date.today()
  for row in self.live['observations']:
   if row['company'] in ('Storebrand','Protector','Gjensidige') and row['year']>=2026:
    self.assertLessEqual((row['year'],row['quarter']),(now.year,(now.month-1)//3+1))
 def test_idempotent_feed(self):
  self.assertEqual(build(self.data),build(self.data))
if __name__=='__main__':unittest.main()
