import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from quarterly_import_contract import verify,COMPANIES
class AutomaticQuarterImportTests(unittest.TestCase):
 def records(self):
  source=json.loads((ROOT/'data/financial_observations.json').read_text())['observations']
  feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())['observations']
  return source,feed
 def test_all_seven_current_published_quarters(self):
  source,feed=self.records()
  result=verify(source,feed,require_norway=False)
  self.assertEqual(set(x['company'] for x in result),set(COMPANIES))
 def test_missing_existing_report_metric_blocks_publication(self):
  source,feed=self.records()
  latest=max((r['year'],r['quarter']) for r in source if r['company']=='Frende' and r['scope']=='group')
  broken=[r for r in source if not (r['company']=='Frende' and r['scope']=='group' and r['period_type']=='quarter' and
       (r['year'],r['quarter'])==latest and r['metric']=='insurance_revenue')]
  with self.assertRaisesRegex(ValueError,'Frende'):
   verify(broken,feed)
 def test_unpublished_quarters_do_not_require_fabricated_observations(self):
  source,feed=self.records()
  result=verify(source,feed,require_norway=False)
  self.assertIn('Q2 2026',next(x['latest_imported'] for x in result if x['company']=='Frende'))
  self.assertIn('Q2 2026',next(x['latest_imported'] for x in result if x['company']=='Sampo'))
 def test_frende_revenue_definition_is_operating_revenue(self):
  source,feed=self.records()
  result=verify(source,feed,require_norway=False)
  self.assertIn('Sum driftsinntekter',next(x['revenues_definition'] for x in result if x['company']=='Frende'))
if __name__=='__main__':unittest.main()
