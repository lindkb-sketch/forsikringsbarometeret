import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from quarterly_ytd import add_tryg_ytd
class TrygYTDTests(unittest.TestCase):
 def sample(self):
  return [dict(company='Tryg',scope='norway',year=2025,quarter=q,period_type='quarter',metric=m,value=v,unit='DKKm' if m!='combined_ratio' else 'percent',source_sheet='Geographical - Quarterly Outlin',source_cell=f'D{q}') for q,vals in enumerate([(100,20,80),(200,50,75),(300,90,70)],1) for m,v in zip(('insurance_revenue','insurance_service_result','combined_ratio'),vals)]
 def test_additive(self):
  rows=add_tryg_ytd(self.sample())
  get=lambda m:next(r for r in rows if r['period_type']=='ytd' and r['quarter']==3 and r['metric']==m)
  self.assertEqual(get('insurance_revenue')['value'],600)
  self.assertEqual(get('insurance_service_result')['value'],160)
  self.assertAlmostEqual(get('combined_ratio')['value'],73.333333,places=4)
  self.assertEqual(len(get('insurance_revenue')['inputs']),3)
 def test_missing_q2_blocks_q3(self):
  rows=add_tryg_ytd([r for r in self.sample() if r['quarter']!=2])
  self.assertFalse(any(r['period_type']=='ytd' and r['quarter']==3 for r in rows))
 def test_idempotent(self):
  once=add_tryg_ytd(self.sample());self.assertEqual(add_tryg_ytd(once),once)
