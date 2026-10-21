import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from quarterly_ytd import derive_ytd,add_tryg_ytd
class TrygYtdRatioTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows=json.loads((ROOT/'data/staged_real_excel_observations.json').read_text())['observations']
 def test_real_excel_q3_ratios(self):
  result=derive_ytd(self.rows,2025,3)
  self.assertAlmostEqual(result['loss_ratio']['value'],74.4,delta=0.3)
  self.assertAlmostEqual(result['expense_ratio']['value'],12.2,delta=0.2)
  self.assertAlmostEqual(result['combined_ratio']['value'],86.6,delta=0.3)
  self.assertAlmostEqual(result['combined_ratio']['value'],result['loss_ratio']['value']+result['expense_ratio']['value'],delta=0.01)
 def test_recalculate_all_periods(self):
  rows=add_tryg_ytd(self.rows)
  metrics={r['metric'] for r in rows if r['company']=='Tryg' and r['year']==2025 and r['quarter']==3 and r['period_type']=='ytd'}
  self.assertTrue({'combined_ratio','loss_ratio','expense_ratio'}<=metrics)
 def test_missing_quarter_no_ratio(self):
  rows=[r for r in self.rows if not (r['company']=='Tryg' and r['year']==2025 and r['quarter']==2 and r['period_type']=='quarter')]
  self.assertNotIn('combined_ratio',derive_ytd(rows,2025,3))
