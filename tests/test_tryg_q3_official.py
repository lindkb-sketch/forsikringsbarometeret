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
 def test_q3_revenue(self):self.assertEqual(self.value(2026,3,"insurance_revenue"),2513)
 def test_q3_service_result(self):self.assertEqual(self.value(2026,3,"insurance_service_result"),601)
 def test_q3_combined_ratio(self):self.assertEqual(self.value(2026,3,"combined_ratio"),76.1)
 def test_ytd_revenue(self):self.assertEqual(self.value(2026,3,"insurance_revenue","ytd"),7272)
 def test_ytd_service_result(self):self.assertEqual(self.value(2026,3,"insurance_service_result","ytd"),1301)
 def test_prior_ytd(self):self.assertEqual(self.value(2025,3,"insurance_revenue","ytd"),6456)
 def test_provenance(self):
  for r in self.rows:
   if r["company"]=="Tryg":self.assertEqual(r["source_page"],36)
