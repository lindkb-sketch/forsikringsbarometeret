#!/usr/bin/env python3
"""Isolated future-quarter contract tests: never publish simulated figures."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gjensidige_publish as g
import protector_publish as p
from protector_kpi_check import extract,METRICS
from import_storebrand_reports import parse_group,parse_norway
class FutureTests(unittest.TestCase):
 def table(self,q,year):
  metrics={
   'Insurance revenue from general insurance':[11000.1,10800.1,32000.1,31000.1],
   'Insurance service result general insurance':[2200.1,2100.1,6300.1,6200.1],
   'Combined ratio':[80.1,81.1,81.1,82.1],
   'Cost ratio':[11.7,12.0,11.8,12.1],
   'Loss ratio, net of reinsurance':[68.4,69.1,69.3,70.0]}
  text='NOK millions\n'+'\n'.join(k+' '+' '.join(str(v) for v in vals) for k,vals in metrics.items())
  return [(4,text)]
 def test_gjensidige_q3_and_q4_group_quarter_and_ytd(self):
  for q in (3,4):
   rows=g.parse_group_table(self.table(q,2026),2026,q,'https://example.com/report.pdf','testhash')
   self.assertEqual(len(rows),20)
   self.assertEqual({r['period_type'] for r in rows},{'quarter','ytd'})
   self.assertEqual({r['metric'] for r in rows if r['period_type']=='quarter' and r['year']==2026},set(g.REQUIRED)|{'loss_ratio'})
   self.assertTrue(all(r['quarter']==q and r['year'] in (2025,2026) for r in rows))
   self.assertTrue(any(r['year']==2025 and r['metric']=='insurance_revenue' for r in rows))
 def test_gjensidige_q4_cover_and_isolated_prepare(self):
  from unittest.mock import patch
  baseline={'observations':[]}
  with patch.object(g,'audit',return_value={'ok':True}),patch.object(g,'discover_quarter',return_value='https://example.com/report.pdf'),patch.object(g,'read_pdf',return_value=[(1,'Gjensidige fourth quarter 2026')]+self.table(4,2026)):
   merged,feed,summary=g.prepare(baseline,(4,),year=2026,downloader=lambda _:b'%PDF-fake')
  self.assertEqual(summary['added'],20)
  self.assertEqual(len(feed['observations']),20)
  self.assertEqual(len(merged['observations']),20)
 def test_protector_q4_and_next_year_kpis(self):
  def table(title):
   periods=['Q1 27','Q4 26','Q3 26','Q2 26','Q1 26']
   return '<div>'+title+'</div><div>'+''.join('<span>'+v+'</span>' for v in periods)+'</div>'+''.join('<div>'+label+'</div>'+''.join('<span>'+str(100+i if metric in ('insurance_revenue','insurance_service_result') else 70+i)+'</span>' for i in range(5)) for label,metric in METRICS.items())
  values=extract(table('Protector')+table('Norway'))
  self.assertIn(('group',2026,4,'insurance_revenue'),values)
  self.assertIn(('norway',2027,1,'combined_ratio'),values)
 def test_protector_wrong_pdf_period_rejected(self):
  with patch('pdfplumber.open') as opener:
   class P:
    def extract_text(self):return 'Protector Q3 2026 only'
   class Doc:
    pages=[P()]
    def __enter__(self):return self
    def __exit__(self,*args):pass
   opener.return_value=Doc()
   with self.assertRaisesRegex(ValueError,'target reporting quarter'):
    p.parse_pdf(b'%PDF-synthetic',2026,4)
 def test_storebrand_q4_group_mock_report(self):
  from import_storebrand_reports import parse_group
  from unittest.mock import patch
  metrics={'Insurance premiums f.o.a.':2896,'Claims ratio':69,'Cost ratio':18,'Combined ratio':87,'Cash return on equity, annualised (%)':14.4,'Solvency II ratio (%)':200}
  def line(k,v):return k+' '+' '.join(str(v+i) for i in range(7))
  pages=['Storebrand Group Q4 2026']+['']*7
  pages[7]='Insurance – Results 2026 Q4 Q3 Q2 Q1\n'+'\n'.join(line(k,v) for k,v in list(metrics.items())[:4])
  pages[4]='Group - Key figures 2026\n'+'\n'.join(line(k,v) for k,v in list(metrics.items())[4:])
  from import_storebrand_reports import row as actual_row
  def mocked_row(text,label,count,parser):
   if label=='Solvency II ratio (%)':return [200+i for i in range(7)]
   return actual_row(text,label,count,parser)
  with patch('import_storebrand_reports.pages',return_value=(pages,'testsha')),patch('import_storebrand_reports.row',side_effect=mocked_row):
   rows=parse_group('fake.pdf',year=2026,quarter=4)
  self.assertTrue(any(r['quarter']==4 and r['year']==2026 and r['metric']=='combined_ratio' for r in rows))
  self.assertTrue(all(r.get('source_document_period','Q4 2026') for r in rows))
  self.assertEqual(next(r['value'] for r in rows if r['year']==2026 and r['quarter']==4 and r['metric']=='combined_ratio' and r['period_type']=='quarter'),87)
 def test_storebrand_future_period_not_silently_mislabelled(self):
  fixture=Path(__file__).resolve().parent/'fixtures/storebrand_asa_q3_2026.pdf'
  with self.assertRaisesRegex(ValueError,'header changed'):
   parse_group(fixture,year=2026,quarter=4)
  fixture=Path(__file__).resolve().parent/'fixtures/storebrand_forsikring_q3_2026.pdf'
  with self.assertRaisesRegex(ValueError,'must remain blank'):
   parse_norway(fixture,year=2026,quarter=4)
 def test_storebrand_norway_annual_does_not_fill_q4(self):
  from import_storebrand_reports import parse_norway_annual_q4
  with self.assertRaisesRegex(ValueError,'must remain blank'):
   parse_norway_annual_q4('annual.pdf','q3.pdf','https://example.com/annual','https://example.com/q3',2026)
if __name__=='__main__':unittest.main()
