import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class OfficialTrygTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rows=json.loads((ROOT/"data/financial_observations.json").read_text())["observations"]
 def value(self,year,quarter,metric,period="quarter"):
  r=[x for x in self.rows if x["company"]=="Tryg" and x["year"]==year and x["quarter"]==quarter and x["metric"]==metric and x["period_type"]==period and x["scope"]=="norway"]
  self.assertEqual(len(r),1)
  return r[0]["value"]
 def test_q3_revenue(self):self.assertAlmostEqual(self.value(2026,3,"insurance_revenue"),2513,delta=1)
 def test_q3_service_result(self):self.assertAlmostEqual(self.value(2026,3,"insurance_service_result"),601,delta=1)
 def test_q3_combined_ratio(self):self.assertAlmostEqual(self.value(2026,3,"combined_ratio"),76.1,delta=0.1)
 def test_ytd_revenue(self):self.assertAlmostEqual(self.value(2026,3,"insurance_revenue","ytd"),7272,delta=1)
 def test_ytd_service_result(self):self.assertAlmostEqual(self.value(2026,3,"insurance_service_result","ytd"),1301,delta=1)
 def test_prior_ytd(self):
  rows=[r for r in self.rows if r['company']=='Tryg' and r['year']==2025 and r['quarter']==3 and r['scope']=='norway' and r['metric']=='insurance_revenue' and r['period_type']=='ytd']
  if rows:self.assertAlmostEqual(rows[0]['value'],6456,delta=1)
  else:self.assertFalse(any(r['company']=='Tryg' and r['year']==2025 and r['quarter']==3 and r['scope']=='norway' and r['period_type']=='ytd' for r in self.rows))
 def test_provenance(self):
  for r in self.rows:
   if r['company']=='Tryg':
    self.assertIsInstance(r['source_page'],int)
    self.assertGreater(r['source_page'],0)
    self.assertTrue(r.get('source_url','').startswith('https://'))
