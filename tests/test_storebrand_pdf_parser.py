import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_storebrand_reports import parse_group,parse_norway,integrate
class TestStorebrandImporter(unittest.TestCase):
 def test_published_values(self):
  # Test the source PDFs directly; GitHub production JSON may not yet contain Q3.
  rows=parse_group(ROOT/'tests/fixtures/storebrand_asa_q3_2026.pdf')+parse_norway(ROOT/'tests/fixtures/storebrand_forsikring_q3_2026.pdf')
  def value(scope,period,metric):
   return next(r['value'] for r in rows if r['company']=='Storebrand' and r['year']==2026 and r['quarter']==3 and r['scope']==scope and r['period_type']==period and r['metric']==metric)
  self.assertEqual(value('group','quarter','insurance_revenue'),2896)
  self.assertEqual(value('group','quarter','combined_ratio'),87)
  self.assertEqual(value('norway','quarter','insurance_revenue'),1550.3)
  self.assertEqual(value('norway','quarter','insurance_service_result'),313.3)
  self.assertEqual(value('norway','ytd','insurance_revenue'),4396.1)
  self.assertEqual(value('norway','quarter','solvency_ratio'),179)
 def test_reject_conflicting_values(self):
  import json
  existing=json.loads((ROOT/'data/financial_observations.json').read_text())
  existing['observations']=[r for r in existing['observations'] if r.get('company')!='Storebrand']
  row=parse_norway(ROOT/'tests/fixtures/storebrand_forsikring_q3_2026.pdf')[0]
  existing['observations'].append(row)
  with self.assertRaisesRegex(ValueError,'Conflicting'):
   integrate(existing,[{**row,'value':row['value']+1}])

class TestStorebrandRatios(unittest.TestCase):
 def test_real_norway_pdf_ratio_and_blank_expense(self):
  import os
  pdf=str(ROOT/'tests/fixtures/storebrand_forsikring_q3_2026.pdf')
  rows=parse_norway(pdf)
  def get(year,period,metric):
   return next(r for r in rows if r['year']==year and r['period_type']==period and r['metric']==metric)
  self.assertAlmostEqual(get(2026,'quarter','combined_ratio')['value'],79.791,places=3)
  self.assertAlmostEqual(get(2026,'ytd','combined_ratio')['value'],83.4444,places=3)
  self.assertEqual(get(2026,'quarter','loss_ratio')['value'],60)
  self.assertEqual(get(2026,'ytd','loss_ratio')['value'],62)
  self.assertFalse(any(r['metric']=='expense_ratio' for r in rows))
  self.assertEqual(get(2026,'quarter','combined_ratio')['status'],'calculated')
  self.assertEqual(get(2026,'quarter','combined_ratio')['source_page'],4)
 def test_no_group_values_in_norway(self):
  import os
  pdf=str(ROOT/'tests/fixtures/storebrand_forsikring_q3_2026.pdf')
  self.assertTrue(all(r['scope']=='norway' and r['source_scope']=='norway' for r in parse_norway(pdf)))
