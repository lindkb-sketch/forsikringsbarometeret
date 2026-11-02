import unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class VerifiedDashboardTests(unittest.TestCase):
 def test_all_seven_sources(self):
  d=json.loads((ROOT/"data/report_sources.json").read_text())
  self.assertEqual({r["company"] for r in d["sources"]},{"Fremtind","Gjensidige","Tryg","Sampo","Frende","Protector","Storebrand"})
 def test_dashboard_renders_observations(self):
  s=(ROOT/"index.html").read_text()
  self.assertNotIn('id="verified-financial-panel"',s)
  self.assertNotIn('id="automated-editorial"',s)
  self.assertNotIn('Løpende oppdateringer fra publiserte kilder',s)
  self.assertIn('src="scripts/quarterly_runtime.js"',s)
  self.assertIn('verified_financial_feed.json',(ROOT/'scripts/quarterly_runtime.js').read_text())

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
  self.assertIn("html+=monCalendar()",s)
  self.assertIn("data/live.json?ts=",s)
  self.assertIn("mon-cal-countdown",s)

 def test_future_quarter_summaries_follow_selected_period(self):
  """Newly published quarters must show source-backed summaries without curated notes."""
  html=(ROOT/'index.html').read_text(encoding='utf-8')
  self.assertIn('const period=selectedLabel()',html)
  self.assertIn('const block=currentEditorial()',html)
  self.assertIn('block?.by_company?.[c]',html)
  self.assertIn('item?.period===period',html)
  self.assertIn("esc(item.reader_summary)",html)
  self.assertIn("safeUrl(item.source_url)",html)
  self.assertIn('item.reader_summary',html)
  self.assertIn('setInterval(refresh,300000)',html)
  data=json.loads((ROOT/'data/quarterly_editorial.json').read_text(encoding='utf-8'))
  for label,block in data.get('periods',{}).items():
   for company,item in block.get('by_company',{}).items():
    with self.subTest(period=label,company=company):
     self.assertEqual(item.get('period'),label)
     self.assertTrue(item.get('summary'))
     self.assertTrue(item.get('source_url','').startswith('https://'))

 def test_company_quarter_directional_summary_has_source_and_period(self):
  html=(ROOT/'index.html').read_text(encoding='utf-8')
  self.assertIn('item.reader_summary',html)
  self.assertIn('notes[0].text',html)
  self.assertIn('item?.period===period && item.summary',html)
  data=json.loads((ROOT/'data/quarterly_editorial.json').read_text(encoding='utf-8'))
  current=data['periods'][data['period']]['by_company']
  for company,item in current.items():
   with self.subTest(company=company):
    self.assertEqual(item['period'],data['period'])
    self.assertTrue(item['summary'])
    self.assertTrue(item['source_url'].startswith('https://'))
    self.assertTrue(item.get('comment'))
