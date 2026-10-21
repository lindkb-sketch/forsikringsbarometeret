import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from company_parsers import ALIASES,identify_metrics,stage_rows
class CompanyParsersTests(unittest.TestCase):
 def test_all_seven(self):self.assertEqual(len(ALIASES),7)
 def test_sampo_underwriting(self):self.assertIn("insurance_service_result",identify_metrics("Sampo","Underwriting result"))
 def test_frende_norwegian(self):self.assertIn("insurance_revenue",identify_metrics("Frende","Inntekter fra forsikringstjenester"))
 def test_protector_revenue(self):self.assertIn("insurance_revenue",identify_metrics("Protector","Insurance revenue"))
 def test_no_automatic_number_assignment(self):
  staged=stage_rows("Sampo",{"pages_with_financial_terms":[{"page":3,"tables":[[["Underwriting result","150","120"]]]}]})
  self.assertEqual(staged[0]["status"],"needs_scope_period_column_review")
  self.assertNotIn("value",staged[0])
