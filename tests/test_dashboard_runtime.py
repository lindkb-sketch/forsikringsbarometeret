"""Regression checks for browser JavaScript and live dashboard integrations."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class DashboardRuntimeTests(unittest.TestCase):
 def test_all_inline_scripts_parse(self):
  html=(ROOT/'index.html').read_text()
  scripts=re.findall(r'<script\b[^>]*>([\s\S]*?)</script>',html,flags=re.I)
  self.assertGreater(len(scripts),5)
  for i,script in enumerate(scripts):
   if not script.strip():continue
   result=subprocess.run(['node','--check'],input=script,text=True,capture_output=True)
   self.assertEqual(result.returncode,0,f'Inline script {i}: {result.stderr}')
 def test_visible_q3_table_uses_audited_data(self):
  html=(ROOT/'index.html').read_text()
  self.assertIn("const d=MON_Q3[r.company]||(MON_Q3[r.company]={})",html)
  self.assertIn("d[key]=fmt(r.value",html)
  self.assertIn("show(current,true)",html)
  self.assertIn("verified_financial_feed.json?ts=",html)
 def test_live_updates_present(self):
  html=(ROOT/'index.html').read_text()
  for key in ('live-report-calendar','mon-cal-countdown','live-editorial-market-updates','quarterly_editorial.json','official_news.json','stock_prices.json','setInterval(refresh,300000)'):
   self.assertIn(key,html)
 def test_q3_protector_storebrand_have_actual_verified_metrics(self):
  import json
  data=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  for company in ('Protector','Storebrand'):
   metrics={r['metric'] for r in data['observations'] if r['company']==company and r['year']==2026 and r['quarter']==3 and r['scope']=='group' and r['period_type']=='quarter'}
   self.assertTrue({'combined_ratio','loss_ratio','expense_ratio'}.issubset(metrics),company)

 def test_live_q3_bridge_accepts_actual_feed_schema(self):
  import json
  html=(ROOT/'index.html').read_text()
  feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  self.assertNotIn("feed.source_policy",html)
  self.assertIn("Array.isArray(feed.observations)",html)
  self.assertGreater(len(feed['observations']),0)
  self.assertNotIn("source_policy",feed)
  for company in ('Protector','Storebrand'):
   q3=[r for r in feed['observations'] if r['company']==company and r['year']==2026 and r['quarter']==3 and r['scope']=='group' and r['period_type']=='quarter' and r['status']=='reported']
   self.assertTrue(q3,company)
  self.assertIn("let period='Q3'",html)
  self.assertIn("if(period==='Q3'){const d=",html)

 def test_q3_revenue_previous_year_profitability_and_brief_are_wired(self):
  html=(ROOT/'index.html').read_text()
  for expected in ("d['revenue'+suffix]=fmt(r.value)","d[key+suffix]=fmt(r.value","profitabilityVerified[c]['Q3 2026']=[loss.value,cost.value,ratio.value]","Forsikringsinntekter · Q3","Q3 2025: ikke verifisert","KVARTALSBRIEF · Q3 2026 · KILDEOPPDATERT"):
   self.assertIn(expected,html)
  import json
  feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  for company in ('Protector','Storebrand'):
   self.assertTrue(any(r['company']==company and r['year']==2026 and r['quarter']==3 and r['metric']=='insurance_revenue' and r['scope']=='group' for r in feed['observations']))
