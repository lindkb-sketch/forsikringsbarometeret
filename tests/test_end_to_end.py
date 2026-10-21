import json,sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from build_verified_feed import build,publish
class EndToEndTests(unittest.TestCase):
 def row(self):
  return {"company":"Tryg","year":2026,"quarter":2,"scope":"group","period_type":"quarter","metric":"insurance_revenue","value":123,"source_url":"https://tryg.com/reports/quarterly-report.pdf","source_page":5,"source_type":"official_quarterly_report","status":"reported"}
 def test_report_observation_to_static_feed(self):
  with tempfile.TemporaryDirectory() as t:
   src=Path(t)/"input.json";dst=Path(t)/"feed.json"
   src.write_text(json.dumps({"observations":[self.row()]}))
   result=publish(dst,src)
   saved=json.loads(dst.read_text())
   self.assertEqual(saved["observations"][0]["value"],123)
   self.assertFalse(result["coverage_complete"])
 def test_invalid_source_never_overwrites(self):
  with tempfile.TemporaryDirectory() as t:
   src=Path(t)/"input.json";dst=Path(t)/"feed.json"
   dst.write_text("previous")
   row=self.row();row["source_type"]="press_release"
   src.write_text(json.dumps({"observations":[row]}))
   with self.assertRaises(ValueError):publish(dst,src)
   self.assertEqual(dst.read_text(),"previous")
 def test_provisional_not_published(self):
  row=self.row();row["status"]="provisional"
  self.assertEqual(build({"observations":[row]})["observations"],[])
 def test_page_uses_verified_feed(self):
  self.assertIn("fetch('data/verified_financial_feed.json'",(ROOT/"index.html").read_text())
