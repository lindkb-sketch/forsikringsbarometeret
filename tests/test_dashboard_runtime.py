"""Regression checks for original dashboard and rolling, source-derived financial views."""
import re
import subprocess
import unittest
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html')
RUNTIME=(ROOT/'scripts/quarterly_runtime.js')

class DashboardRuntimeTests(unittest.TestCase):
 def test_all_scripts_parse(self):
  html=HTML.read_text()
  inline=re.findall(r'<script\b[^>]*>([\s\S]*?)</script>',html,flags=re.I)
  self.assertGreater(len(inline),5)
  for i,s in enumerate(inline):
   if s.strip():
    cmd=subprocess.run(['node','--check'],input=s,text=True,capture_output=True)
    self.assertEqual(cmd.returncode,0,f'Inline {i}: {cmd.stderr}')
  cmd=subprocess.run(['node','--check',str(RUNTIME)],text=True,capture_output=True)
  self.assertEqual(cmd.returncode,0,cmd.stderr)

 def test_original_dashboard_design_is_preserved(self):
  html=HTML.read_text()
  for token in ('quarter-changes-grid strategic-grid','media-news-grid',
                'profitability-panel','cr-podium-panel','results-comparison',
                'kpi-seven dynamic-kpis','id="verified-q3-dashboard-bridge"'):
   self.assertIn(token,html)
  self.assertNotIn('source-driven-home-style',html)
  self.assertNotIn('src="scripts/live_dashboard.js"',html)

 def test_live_sources_and_rolling_periods(self):
  html=HTML.read_text()
  js=RUNTIME.read_text()
  for token in ('live-report-calendar','live-editorial-market-updates',
                'quarterly_editorial.json','official_news.json','stock_prices.json'):
   self.assertIn(token,html)
  for token in ('verified_financial_feed.json?t=','periodList=calcPeriods()',
                'quarterTimeline(selection)','year-1,quarter','MON_SELECT=()=>',
                'isSameBasis','setInterval(refresh,300000)'):
   self.assertIn(token,js)
  self.assertIn('const displayedQuarters=profitabilityQuarters.slice(-5)',html)

 def test_calendar_hidden_for_historical_quarter(self):
  html=HTML.read_text()
  # The live calendar must follow the user's chosen quarter, not merely the
  # latest available data period. Historical navigation hides the entire panel.
  self.assertIn('const selected=window.FBQuarterly?.period;',html)
  self.assertIn("selected.year!==latest.year||selected.quarter!==latest.quarter)return '';",html)

 def test_strategic_headlines_require_concrete_events(self):
  html=HTML.read_text()
  self.assertIn('strategicCategories',html)
  self.assertIn('strategicNoise',html)
  self.assertIn('all.filter(r=>strategicCategory(r))',html)
  self.assertIn('Mulig strategisk hendelse basert på overskrift.',html)
  self.assertNotIn('strategicPattern.test(r.headline)',html)

 def test_strategy_blends_issuer_sources_with_distinct_media(self):
  html=HTML.read_text()
  self.assertIn("currentEditorial()?.brief||[]",html)
  self.assertIn("r?.basis==='issuer_commentary'",html)
  self.assertIn('const cards=officialCards+mediaCards;',html)
  self.assertIn("Math.max(0,3-selectedOfficial.length)",html)
  self.assertIn('Selskapets primærkilde',html)
  self.assertIn("!selectedMedia.some(x=>equivalent(x,r))",html)

 def test_automatic_strategy_refresh_and_source_integrity(self):
  html=HTML.read_text()
  main=(ROOT/'.github/workflows/update.yml').read_text()
  commentary=(ROOT/'.github/workflows/quarterly-commentary.yml').read_text()
  pipeline=(ROOT/'scripts/run_pipeline.py').read_text()
  self.assertIn("cron: '17,47 * * * *'",main)
  self.assertIn("cron: '25 3,9,15,21 * * *'",commentary)
  self.assertIn('python scripts/ingest_media_news.py',main)
  self.assertIn('refresh_report_commentary.py',pipeline)
  self.assertIn('build_editorial.py',pipeline)
  self.assertIn('data/quarterly_editorial.json',main)
  self.assertIn('data/official_news.json',main)
  self.assertIn("['quarterly_editorial.json','official_news.json','stock_prices.json']",html)
  self.assertIn('setInterval(refresh,300000)',html)
  self.assertIn('const cards=officialCards+mediaCards;',html)

 def test_q3_feed_is_verified_and_has_metrics(self):
  d=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  self.assertGreater(len(d['observations']),0)
  for company in ('Fremtind','Gjensidige','Tryg','Protector','Storebrand'):
   rows=[r for r in d['observations'] if r['company']==company and r['year']==2026
         and r['quarter']==3 and r['scope']=='group' and r['period_type']=='quarter']
   self.assertIn('combined_ratio',{r['metric'] for r in rows},company)

 def test_no_hardcoded_active_financial_series(self):
  js=RUNTIME.read_text()
  self.assertNotIn('2026 && r.quarter===3',js)
  self.assertIn('periodList=calcPeriods()',js)
  self.assertIn('profitabilityVerified[name][l]=[loss,cost,cr]',js)

if __name__=='__main__':
 unittest.main()
