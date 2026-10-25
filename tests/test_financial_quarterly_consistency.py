"""Recurring financial invariants; executed in every full GitHub Actions unit test run."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_financials import audit

def comparable(a,b):
 def apm(r):return 'not ifrs insurance revenue' in str(r.get('source_definition','')).lower() or 'premiums f.o.a.' in str(r.get('source_definition','')).lower()
 return a.get('unit')==b.get('unit') and apm(a)==apm(b)

class QuarterlyConsistencyTests(unittest.TestCase):
 def test_every_imported_financial_observation_passes_source_audit(self):
  data=json.loads((ROOT/'data/financial_observations.json').read_text())
  result=audit(data)
  self.assertTrue(result['ok'],result['errors'])
 def test_reported_revenue_growth_agrees_with_comparable_report_table(self):
  data=json.loads((ROOT/'data/financial_observations.json').read_text())
  index={(r['company'],r['year'],r['quarter'],r['scope'],r['period_type'],r['metric']):r for r in data['observations'] if r['scope'] in ('group','norway')}
  for key,r in index.items():
   c,y,q,scope,period,metric=key
   if metric!='insurance_revenue' or r['value']<=0:continue
   last=index.get((c,y-1,q,scope,period,metric))
   published=index.get((c,y,q,scope,period,'insurance_revenue_growth'))
   if last and published and last['value']>0 and comparable(r,last):
    calculated=(r['value']/last['value']-1)*100
    self.assertAlmostEqual(calculated,published['value'],delta=0.15,msg=f'{c} {y} Q{q} {period}')
 def test_solvency_does_not_conflict_across_quarter_and_ytd(self):
  data=json.loads((ROOT/'data/financial_observations.json').read_text())
  rows={(r['company'],r['year'],r['quarter'],r['scope'],r['period_type']):r for r in data['observations'] if r['metric']=='solvency_ratio'}
  for (c,y,q,scope,period),r in rows.items():
   other=rows.get((c,y,q,scope,'ytd' if period=='quarter' else 'quarter'))
   if other:
    self.assertEqual(r['value'],other['value'],f'{c} {y} Q{q} solvency is point-in-time')
 def test_fremtind_q3_revenue_growth_from_reported_comparisons(self):
  data=json.loads((ROOT/'data/financial_observations.json').read_text())
  rows={(r['year'],r['metric']):r['value'] for r in data['observations'] if r['company']=='Fremtind' and r['scope']=='group' and r['quarter']==3 and r['period_type']=='quarter'}
  self.assertAlmostEqual((rows[2026,'insurance_revenue']/rows[2025,'insurance_revenue']-1)*100,4.266,delta=0.01)

if __name__=='__main__':unittest.main()
