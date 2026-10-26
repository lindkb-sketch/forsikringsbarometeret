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

 def test_publication_dates_heading_is_visible_in_active_calendar(self):
  html=HTML.read_text()
  self.assertIn('Publiseringsdatoer for kvartalsrapporter · ',html)
  self.assertIn('class="mon-calendar-top"',html)
  self.assertIn('const selected=window.FBQuarterly?.period;',html)
  self.assertNotIn('.mon-calendar-top h2{display:none',html)

 def test_strategic_headlines_require_concrete_events(self):
  html=HTML.read_text()
  self.assertIn('strategicCategories',html)
  self.assertIn('strategicNoise',html)
  self.assertNotIn('const mediaCards=groups.strategic.map',html)
  self.assertNotIn('Mulig strategisk hendelse basert på overskrift.',html)
  self.assertNotIn('strategicPattern.test(r.headline)',html)

 def test_unified_media_and_verified_market_insight(self):
  html=HTML.read_text()
  self.assertIn("quarterChanges=function(){return '';};",html)
  self.assertIn('const strategic=groups.official.map(x=>',html)
  self.assertIn('const articles=groups.other.map(x=>',html)
  self.assertIn('Nyheter og kildeverifisert innsikt i konkurransebildet',html)
  self.assertIn('Les primærkilden',html)
  self.assertNotIn('Mulig strategisk hendelse basert på overskrift.',html)
  self.assertIn('const other=all.slice(0,4);',html)
  self.assertIn("r?.basis==='rule_verified_issuer_narrative'",html)
  self.assertNotIn('const official=(currentEditorial()?.brief||[]).filter',html)

 def test_unified_media_automatic_refresh_and_free_sources(self):
  html=HTML.read_text()
  main=(ROOT/'.github/workflows/update.yml').read_text()
  commentary=(ROOT/'.github/workflows/quarterly-commentary.yml').read_text()
  pipeline=(ROOT/'scripts/run_pipeline.py').read_text()
  self.assertIn("cron: '17,47 * * * *'",main)
  self.assertIn("cron: '25 3,9,15,21 * * *'",commentary)
  self.assertIn('python scripts/ingest_media_news.py',main)
  self.assertIn('refresh_report_commentary.py',pipeline)
  self.assertIn('build_strategic_market.py',pipeline)
  self.assertIn("['quarterly_editorial.json','official_news.json','stock_prices.json','strategic_market.json']",html)
  self.assertIn('setInterval(refresh,300000)',html)
  self.assertNotIn('python scripts/ai_strategic_editor.py',main)

 def test_current_and_prior_year_growth_cover_quarter_and_ytd(self):
  js=RUNTIME.read_text()
  self.assertIn("for(const [type,bucket] of [['quarter',MON_Q3],['ytd',MON_YTD_Q3]])",js)
  self.assertIn("const thisGrowth=growthFor(year),lastGrowth=growthFor(year-1)",js)
  self.assertIn("quote(name,type,targetYear-1,quarter,'insurance_revenue')",js)
  self.assertIn("if(lastGrowth){",js)
  self.assertIn("data.growthPrev=fmt(lastGrowth.value,true)",js)
  self.assertIn("data.growthComparisonPeriod=type",js)
  self.assertIn("!isSameBasis(now,before)",js)
  html=HTML.read_text()
  self.assertIn("period==='H3'?MON_YTD_Q3[c]:MON_Q3[c]",html)
 def test_frende_operating_revenue_rolls_without_hardcoded_values(self):
  html=HTML.read_text()
  js=RUNTIME.read_text()
  importer=(ROOT/'scripts/import_frende_holding.py').read_text()
  self.assertIn("if(key==='growth'&&c==='Frende')",html)
  self.assertIn("label.textContent='Vekst i forsikringsinntekter (IFRS 4)'",html)
  self.assertIn("data.growthMetricLabel='Vekst i forsikringsinntekter (IFRS 4)'",js)
  self.assertIn("name==='Frende'?'Beregnet fra kildeverifiserte, sammenlignbare driftsinntekter'",js)
  self.assertIn("label='Sum driftsinntekter'",importer)
  self.assertIn("header[1]!=f'{quarter}. kv {year}'",importer)
  self.assertIn("growthFor(year-1)",js)
  self.assertNotIn("if(year===2026&&quarter===3)",js)
 def test_prior_year_values_are_visible_in_quarter_and_ytd(self):
  html=HTML.read_text()
  js=RUNTIME.read_text()
  self.assertIn("period==='H3'?MON_YTD_Q3[c]:MON_Q3[c]",html)
  self.assertIn("data[k+'Prev']=fmt(prior.value",js)
  d=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  rows=d['observations']
  for q in (1,2,3):
   for period in ('quarter','ytd'):
    for metric in ('insurance_revenue','solvency_ratio'):
     current=[r for r in rows if r['company']=='Fremtind' and r['year']==2026 and r['quarter']==q and r['scope']=='group' and r['period_type']==period and r['metric']==metric]
     prior=[r for r in rows if r['company']=='Fremtind' and r['year']==2025 and r['quarter']==q and r['scope']=='group' and r['period_type']==period and r['metric']==metric]
     self.assertEqual(len(current),1,(q,period,metric,'current'))
     self.assertEqual(len(prior),1,(q,period,metric,'previous'))
 def test_q3_feed_is_verified_and_has_metrics(self):
  d=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  self.assertGreater(len(d['observations']),0)
  for company in ('Fremtind','Gjensidige','Tryg','Protector','Storebrand'):
   rows=[r for r in d['observations'] if r['company']==company and r['year']==2026
         and r['quarter']==3 and r['scope']=='group' and r['period_type']=='quarter']
   self.assertIn('combined_ratio',{r['metric'] for r in rows},company)

 def test_unpublished_current_quarter_hides_prior_growth(self):
  runtime=RUNTIME.read_text()
  self.assertIn("const currentReported=Boolean(d.revenue)",runtime)
  self.assertIn("Ikke publisert",runtime)
  self.assertIn("const currentGrowth=currentReported?d.growth:null",runtime)
  self.assertIn("const previousGrowth=currentReported?d.growthPrev:null",runtime)
  self.assertIn("if(bucket[company]?.revenue&&bucket[company]?.revenueBasis)",runtime)
  self.assertIn("if(localStorebrand&&bucket.Storebrand?.revenue)",runtime)

 def test_storebrand_explanation_below_table_and_frende_ifrs4_label(self):
  runtime=RUNTIME.read_text()
  html=HTML.read_text()
  self.assertIn("const basis='';",runtime)
  self.assertIn("notesRow.appendChild(note)",runtime)
  self.assertIn("notesRow.className='revenue-basis-notes'",runtime)
  self.assertIn("Vekst i forsikringsinntekter (IFRS 4)",runtime)
  self.assertIn("Vekst i forsikringsinntekter (IFRS 4)",html)

 def test_no_hardcoded_active_financial_series(self):
  js=RUNTIME.read_text()
  self.assertNotIn('2026 && r.quarter===3',js)
  self.assertIn('periodList=calcPeriods()',js)
  self.assertIn('profitabilityVerified[name][l]=[loss,cost,cr]',js)

if __name__=='__main__':
 unittest.main()
