import unittest,sys,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_editorial
class ArrivalTests(unittest.TestCase):
 def test_new_q3_company_sources_change_brief_and_future_rollover(self):
  def row(c,q):
   return dict(company=c,year=2026,quarter=q,scope='group',period_type='quarter',metric='combined_ratio',value=85,unit='percent',status='reported',source_url='https://reports.example.com/'+c+'.pdf')
  def note(c,theme):
   return dict(theme=theme,text=c+' beskriver en viktig og kildebelagt utvikling i kvartalet.',companies=[c],sources=[dict(company=c,url='https://reports.example.com/'+c+'.pdf',kind='official_quarterly_report')])
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data').mkdir()
   def build(rows,notes):
    (root/'data/quarterly_insights.json').write_text(json.dumps({'periods':notes}))
    with patch.object(build_editorial,'ROOT',root):
     return build_editorial.build({'observations':rows},{'items':[]})
   old=['Fremtind','Gjensidige','Tryg','Protector','Storebrand']
   initial=[note(c,t) for c,t in zip(old,['large_claims','growth','profitability','strategy','competition'])]
   before=build([row(c,3) for c in old],{'Q3 2026':initial})
   arrivals=[note('Frende','reserves'),note('Sampo','weather')]
   after=build([row(c,3) for c in old+['Frende','Sampo']],{'Q3 2026':initial+arrivals})
   self.assertEqual(after['periods']['Q3 2026']['reported_company_count'],7)
   self.assertEqual(after['period'],'Q3 2026')
   featured={c for v in after['brief'] for c in v['companies']}
   self.assertTrue({'Frende','Sampo'}.issubset(featured),featured)
   self.assertNotEqual(before['brief'],after['brief'])
   self.assertLessEqual(len(after['brief']),4)
   self.assertLessEqual(sum(len(v['text'].split()) for v in after['brief']),220)
   q4=build([row(c,3) for c in old+['Frende','Sampo']]+[row('Tryg',4)],{'Q3 2026':initial+arrivals,'Q4 2026':[note('Tryg','weather')]})
   self.assertEqual(q4['period'],'Q4 2026')
   self.assertEqual(q4['periods']['Q4 2026']['reported_company_count'],1)
   self.assertIn('Q3 2026',q4['periods'])
if __name__=='__main__':unittest.main()
