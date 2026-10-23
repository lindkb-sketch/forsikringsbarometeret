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
 def test_percentage_not_allowed_as_amount_unit(self):
  r=self.row();r["unit"]="percent"
  self.assertFalse(audit({"observations":[r]})["ok"])
 def test_currency_not_allowed_as_ratio_unit(self):
  r=self.row();r["metric"]="combined_ratio";r["unit"]="MNOK"
  self.assertFalse(audit({"observations":[r]})["ok"])
 def test_group_source_not_allowed_for_norway(self):
  r=self.row();r["scope"]="norway";r["source_scope"]="group"
  self.assertFalse(audit({"observations":[r]})["ok"])
 def test_legacy_unspecified_unit_does_not_break_previous_records(self):
  r=self.row()
  self.assertTrue(audit({"observations":[r]})["ok"])
if __name__=="__main__":unittest.main()
