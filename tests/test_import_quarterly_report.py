import unittest,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from import_quarterly_report import import_batch
class ImportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)/"batch.json"
 def tearDown(self):self.tmp.cleanup()
 def row(self):
  return dict(company="Tryg",year=2030,quarter=1,scope="group",period_type="quarter",metric="insurance_revenue",value=123,source_url="https://example.org/q1-quarterly-report.pdf",source_page=5,source_type="official_quarterly_report")
 def test_valid_dry_run(self):
  self.p.write_text(json.dumps({"source_policy":"official_quarterly_report_only","observations":[self.row()]}))
  self.assertFalse(import_batch(self.p,commit=False)["coverage_complete"])
 def test_reject_press_release(self):
  r=self.row();r["source_type"]="press_release"
  self.p.write_text(json.dumps({"source_policy":"official_quarterly_report_only","observations":[r]}))
  with self.assertRaises(ValueError):import_batch(self.p,commit=False)
 def test_reject_existing_key(self):
  r=self.row();r.update(company="Storebrand",year=2026,quarter=2,metric="return_on_equity")
  self.p.write_text(json.dumps({"source_policy":"official_quarterly_report_only","observations":[r]}))
  with self.assertRaises(ValueError):import_batch(self.p,commit=False)
 def test_reject_missing_policy(self):
  self.p.write_text(json.dumps({"observations":[self.row()]}))
  with self.assertRaises(ValueError):import_batch(self.p,commit=False)
