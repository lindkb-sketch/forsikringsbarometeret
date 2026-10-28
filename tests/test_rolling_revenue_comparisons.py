"""Regression contract for rolling quarter vs YTD revenue growth comparisons.

Use source-verified observations; never insert test values into production feeds.
"""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_financials import audit
from quarterly_import_contract import COMPANIES

def basis(row):
 definition=(row.get('source_definition') or '').lower()
 if 'sum driftsinntekter' in definition or 'group operating revenue' in definition:return 'operating'
 if any(x in definition for x in ('not ifrs insurance revenue','segment premiums','premiums f.o.a.')):return 'apm'
 return 'insurance'

def get(rows,name,period,year,q,metric):
 return next((r for r in rows if r.get('company')==name and r.get('scope')=='group'
  and r.get('period_type')==period and r.get('year')==year and r.get('quarter')==q
  and r.get('metric')==metric),None)

class RollingRevenueComparisonTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows=json.loads((ROOT/'data/verified_financial_feed.json').read_text())['observations']
 def test_2025_growth_uses_2025_and_2024_same_period_only(self):
  observed=[]
  for company in COMPANIES:
   for period in ('quarter','ytd'):
    a=get(self.rows,company,period,2025,3,'insurance_revenue')
    b=get(self.rows,company,period,2024,3,'insurance_revenue')
    if not a or not b:continue
    self.assertEqual(a['unit'],b['unit'],(company,period,'unit'))
    self.assertEqual(basis(a),basis(b),(company,period,'basis'))
    self.assertGreater(b['value'],0)
    growth=(a['value']/b['value']-1)*100
    self.assertTrue(-100<growth<1000,(company,period,'unreasonable computed growth'))
    observed.append((company,period))
  self.assertIn(('Fremtind','quarter'),observed)
  self.assertIn(('Fremtind','ytd'),observed)
  self.assertIn(('Frende','quarter'),observed)
  self.assertIn(('Frende','ytd'),observed)
 def test_runtime_has_separate_annual_growth_with_no_quarter_ytd_mixing(self):
  js=(ROOT/'scripts/quarterly_runtime.js').read_text()
  self.assertIn("for(const [type,bucket] of [['quarter',MON_Q3],['ytd',MON_YTD_Q3]])",js)
  self.assertIn("const thisGrowth=growthFor(year),lastGrowth=growthFor(year-1)",js)
  self.assertIn("quote(name,type,targetYear-1,quarter,'insurance_revenue')",js)
  self.assertIn("!isSameBasis(now,before)",js)
 def test_observations_are_source_audited(self):
  self.assertTrue(audit({'observations':self.rows})['ok'])
if __name__=='__main__':unittest.main()
