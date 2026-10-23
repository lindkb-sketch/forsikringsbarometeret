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

 def test_all_seven_are_visible_as_clickable_company_selectors(self):
  s=(ROOT/'index.html').read_text()
  self.assertIn('function companyQuickNav()',s)
  self.assertIn("const names=['Fremtind',...companies]",s)
  self.assertIn("'Protector','Storebrand'",s)
  self.assertIn('company-quick-link',s)
  self.assertIn('aria-label="Vis ${c}"',s)
  self.assertIn('grid-template-columns:repeat(2,minmax(0,1fr))',s)

 def test_verified_q3_values_reach_visible_comparison(self):
  s=(ROOT/'index.html').read_text()
  self.assertIn('id="verified-q3-dashboard-bridge"',s)
  self.assertIn("const KEYS={combined_ratio:'cr',loss_ratio:'loss'",(ROOT/"scripts/quarterly_runtime.js").read_text())
  self.assertIn("data[k+'Prev']",(ROOT/"scripts/quarterly_runtime.js").read_text())
  self.assertIn("show(current,true)",s)
  self.assertIn("setInterval(refresh,300000)",(ROOT/"scripts/quarterly_runtime.js").read_text())
 def test_calendar_is_present_on_dashboard(self):
  s=(ROOT/'index.html').read_text()
  self.assertIn("monCalendar()",s)
  self.assertIn("html+monCalendar()",s)
  self.assertIn("data/live.json?ts=",s)
  self.assertIn("mon-cal-countdown",s)
