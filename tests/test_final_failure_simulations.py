"""Fail-closed source validation regressions for invalid historic replay inputs."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_financials import audit
from build_verified_feed import build
from gjensidige_report_check import official_report_links
from import_tryg import parse_group
class FaultSimulation(unittest.TestCase):
 def row(self):
  return dict(company="Gjensidige",year=2026,quarter=3,scope="group",
      period_type="quarter",metric="insurance_revenue",value=100,unit="MNOK",
      status="reported",source_type="official_quarterly_report",
      source_url="https://www.gjensidige.com/report.pdf",source_page=5,
      source_sha256="verified-document-digest")
 def test_missing_source_link_cannot_be_imported(self):
  self.assertEqual(official_report_links("<html>Not published</html>","https://www.gjensidige.com/",3,2026),[])
 def test_mislabeled_period_blocked(self):
  row=self.row();row["quarter"]=5
  with self.assertRaises(ValueError):build({"observations":[row]})
 def test_untrusted_source_blocked(self):
  row=self.row();row["source_url"]="http://unknown.example/report.pdf"
  self.assertFalse(audit({"observations":[row]})["ok"])
 def test_wrong_unit_blocked(self):
  row=self.row();row["unit"]="percent"
  self.assertFalse(audit({"observations":[row]})["ok"])
 def test_invalid_pdf_cannot_parse_as_tryg(self):
  with self.assertRaises(ValueError):parse_group(b"not a PDF",2026,3,"https://tryg.com/report.pdf")
 def test_duplicate_cannot_be_published(self):
  row=self.row()
  with self.assertRaises(ValueError):build({"observations":[row,row.copy()]})
if __name__=="__main__":unittest.main()
