"""Regression checks for browser JavaScript and live dashboard integrations."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class DashboardRuntimeTests(unittest.TestCase):
 def test_all_inline_scripts_parse(self):
  html=(ROOT/'index.html').read_text()
  scripts=re.findall(r'<script\\b[^>]*>([\\s\\S]*?)</script>',html,flags=re.I)
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
