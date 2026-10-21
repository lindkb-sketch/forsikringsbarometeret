import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_financials import audit
class SourceGuards(unittest.TestCase):
 def row(self):
  return dict(company="Tryg",year=2026,quarter=2,scope="group",period_type="quarter",metric="insurance_revenue",value=100,source_url="https://example.com/q2-quarterly-report.pdf",source_page=5,source_type="official_quarterly_report")
 def test_press_release_url_rejected_even_if_mislabeled(self):
  r=self.row();r["source_url"]="https://example.com/press-release.pdf"
  self.assertFalse(audit({"observations":[r]})["ok"])
 def test_calculated_without_inputs_rejected(self):
  r=self.row();r["status"]="calculated"
  self.assertFalse(audit({"observations":[r]})["ok"])
 def test_missing_cells_reported(self):
  result=audit({"observations":[]})
  self.assertEqual(len(result["missing_cells"]),7*2*2*7)
  self.assertFalse(result["coverage_complete"])
if __name__=="__main__":unittest.main()
