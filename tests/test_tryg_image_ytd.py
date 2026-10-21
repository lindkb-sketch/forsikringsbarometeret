import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from quarterly_ytd import derive_ytd
class TrygImageYTD(unittest.TestCase):
 def setUp(self):
  data=json.loads((ROOT/'tests/fixtures/tryg_user_image_norway.json').read_text())
  self.rows=[]
  for period,metrics in data['quarters'].items():
   for metric,value in metrics.items():
    self.rows.append(dict(company='Tryg',scope='norway',year=int(period[:4]),quarter=int(period[-1]),period_type='quarter',metric=metric,value=value,unit='DKKm' if metric!='combined_ratio' else 'percent'))
 def test_2026_ytd_q3(self):
  ytd=derive_ytd(self.rows,2026,3)
  self.assertEqual(ytd['insurance_revenue']['value'],7272)
  self.assertEqual(ytd['insurance_service_result']['value'],1301)
  self.assertIn('combined_ratio',ytd)
  self.assertGreater(ytd['combined_ratio']['value'],0)
 def test_2025_ytd_q3(self):
  ytd=derive_ytd(self.rows,2025,3)
  self.assertEqual(ytd['insurance_revenue']['value'],6456)
  self.assertEqual(ytd['insurance_service_result']['value'],860)
 def test_missing_quarter_does_not_generate_ytd(self):
  rows=[r for r in self.rows if not (r['year']==2026 and r['quarter']==2)]
  self.assertFalse(derive_ytd(rows,2026,3))
