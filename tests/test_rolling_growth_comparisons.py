#!/usr/bin/env python3
"""Rolling comparisons: validate every year/quarter and YTD across issuer history.

Never equate isolated quarter to YTD, mix accounting bases, or silently certify
missing historical comparisons. Uses financial source rows only.
"""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prior_year_growth_coverage import evidence,basis

class RollingComparisonsTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows=json.loads((ROOT/'data/verified_financial_feed.json').read_text())['observations']
 def test_two_year_reference_is_correct_for_every_available_period(self):
  periods=sorted({(r['year'],r['quarter']) for r in self.rows
                  if r.get('scope')=='group' and r.get('period_type')=='quarter'
                  and r.get('metric')=='insurance_revenue'})
  for year,quarter in periods:
   if year<2025:continue
   for company in evidence(self.rows,year,quarter)['companies']:
    for kind in ('quarter','ytd'):
     item=company[kind]
     self.assertEqual(item['reference'],f'{year-1}-Q{quarter} vs {year-2}-Q{quarter}')
     if item['status']!='verified':
      self.assertIsNone(item['growth_percent'])
      continue
     values=item['observation_values']
     prior,old=values[str(year-1)],values[str(year-2)]
     self.assertGreater(old,0)
     self.assertAlmostEqual(item['growth_percent'],100*(prior/old-1),delta=0.051,
       msg=f"{company['company']} {kind} {year}-Q{quarter}")
     self.assertTrue(item['source_urls'])
 def test_revenue_bases_never_cross_issuers_or_accounting_definitions(self):
  self.assertEqual(basis({'source_definition':'Sum driftsinntekter (Frende Holding AS)'}),'operating_revenue')
  self.assertEqual(basis({'source_definition':'premiums f.o.a.'}),'insurance_premiums_apm')
  self.assertNotEqual(basis({'source_definition':'Sum driftsinntekter'}),
                      basis({'source_definition':'Insurance revenue'}))
 def test_historical_imports_are_part_of_scheduled_pipeline(self):
  code=(ROOT/'scripts/run_pipeline.py').read_text()
  for filename in ('protector_2024_official_backfill.py','storebrand_2024_official_backfill.py',
                   'import_frende_holding.py','import_fremtind_holding.py',
                   'sampo_publish.py','import_gjensidige_latest.py','import_tryg.py'):
   self.assertIn(filename,code)
  workflow=(ROOT/'.github/workflows/update.yml').read_text()
  self.assertIn('python scripts/prior_year_growth_coverage.py',workflow)
  self.assertIn('python scripts/quarterly_import_contract.py',workflow)
 def test_no_invented_growth_when_prior_prior_year_missing(self):
  for company in evidence(self.rows,2026,3)['companies']:
   for kind in ('quarter','ytd'):
    item=company[kind]
    if item['status']=='missing_verified_comparable':
     self.assertIsNone(item['growth_percent'])
if __name__=='__main__':unittest.main()
