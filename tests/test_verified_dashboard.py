import unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class VerifiedDashboardTests(unittest.TestCase):
 def test_all_seven_sources(self):
  d=json.loads((ROOT/"data/report_sources.json").read_text())
  self.assertEqual({r["company"] for r in d["sources"]},{"Fremtind","Gjensidige","Tryg","Sampo","Frende","Protector","Storebrand"})
 def test_dashboard_renders_observations(self):
  s=(ROOT/"index.html").read_text()
  self.assertIn('id="verified-financial-panel"',s)
  self.assertIn("data/verified_financial_feed.json",s)
  self.assertIn("r.source_page",s)
