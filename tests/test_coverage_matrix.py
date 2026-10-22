import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_financials import audit
class CoverageMatrixTests(unittest.TestCase):
 def test_five_roe_not_full_coverage(self):
  from json import loads
  data=loads((Path(__file__).resolve().parents[1]/"data/financial_observations.json").read_text())
  result=audit(data)
  self.assertFalse(result["coverage_complete"])
  self.assertEqual(result["coverage_matrix"]["Storebrand"]["group"]["quarter"]["return_on_equity"],"reported")
  self.assertEqual(result["coverage_matrix"]["Storebrand"]["group"]["quarter"]["combined_ratio"],"reported")
  self.assertEqual(result["coverage_matrix"]["Protector"]["group"]["quarter"]["combined_ratio"],"missing_or_not_applicable")
 def test_empty_model_not_complete(self):
  self.assertFalse(audit({"observations":[]})["coverage_complete"])
