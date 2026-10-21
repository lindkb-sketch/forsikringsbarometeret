import json,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_financials import audit
class FinancialAuditTests(unittest.TestCase):
 def base(self):
  return {"observations":[]}
 def row(self,metric,value,year=2026):
  return dict(company="Tryg",year=year,quarter=3,scope="group",period_type="quarter",metric=metric,value=value,source_url="https://tryg.com/official.pdf",source_page=8,source_type="official_quarterly_report")
 def test_reject_press_release(self):
  d=self.base();r=self.row("insurance_revenue",100);r["source_type"]="press_release";d["observations"]=[r]
  self.assertFalse(audit(d)["ok"])
 def test_growth(self):
  d=self.base();d["observations"]=[self.row("insurance_revenue",110),self.row("insurance_revenue",100,2025)]
  self.assertAlmostEqual(audit(d)["derived_growth"][0]["value"],10)
 def test_reject_duplicate(self):
  d=self.base();r=self.row("insurance_revenue",100);d["observations"]=[r,r]
  self.assertFalse(audit(d)["ok"])
 def test_reject_cr_mismatch(self):
  d=self.base();d["observations"]=[self.row("combined_ratio",70),self.row("loss_ratio",60),self.row("expense_ratio",15)]
  self.assertFalse(audit(d)["ok"])
 def test_missing_coverage(self):
  self.assertFalse(audit(self.base())["coverage_complete"])
if __name__=="__main__":unittest.main()
