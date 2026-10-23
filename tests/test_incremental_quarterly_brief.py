"""Quarterly commentary accumulates issuer findings as new companies report."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_editorial

class IncrementalQuarterlyBriefTests(unittest.TestCase):
 def row(self,c):
  return {'company':c,'year':2027,'quarter':1,'scope':'group','period_type':'quarter','metric':'combined_ratio','value':83,'unit':'percent','source_url':'https://reports.example.com/'+c+'.pdf','status':'reported'}
 def test_new_company_adds_to_existing_quarter_without_erasing_insights(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';data.mkdir()
   one={'theme':'large_claims','text':'Fremtind rapporterer at store enkeltskader påvirket kvartalets skadeutvikling.','companies':['Fremtind'],'sources':[{'company':'Fremtind','url':'https://reports.example.com/Fremtind.pdf','kind':'official_quarterly_report'}]}
   two={'theme':'strategy','text':'Tryg beskriver nye distribusjonstiltak som et strategisk satsingsområde.','companies':['Tryg'],'sources':[{'company':'Tryg','url':'https://reports.example.com/Tryg.pdf','kind':'official_quarterly_report'}]}
   with patch.object(build_editorial,'ROOT',Path(d)):
    (data/'quarterly_insights.json').write_text(json.dumps({'periods':{'Q1 2027':[one]}}))
    first=build_editorial.build({'observations':[self.row('Fremtind')]},{'items':[]})
    self.assertEqual([x['theme'] for x in first['brief']],['large_claims'])
    (data/'quarterly_insights.json').write_text(json.dumps({'periods':{'Q1 2027':[one,two]}}))
    second=build_editorial.build({'observations':[self.row('Fremtind'),self.row('Tryg')]},{'items':[]})
    self.assertEqual({x['theme'] for x in second['brief']},{'large_claims','strategy'})
    self.assertEqual(second['period'],'Q1 2027')
 def test_brief_remains_short_when_many_companies_arrive(self):
  rows=[{'text':f'Tema {i}: '+('dokumentert innsikt '*20),'theme':f'theme_{i}','basis':'issuer_commentary','source_url':'https://example.com/report.pdf'} for i in range(18)]
  selected=build_editorial.concise_brief(rows)
  self.assertLessEqual(len(selected),4)
  self.assertLessEqual(sum(len(r['text'].split()) for r in selected),220)
  self.assertEqual(len(rows),18)
 def test_raw_pdf_excerpt_is_evidence_not_published_prose(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';data.mkdir()
   raw={'theme':'weather','basis':'issuer_pdf_verbatim',
        'text':'Fremtind omtaler i kvartalsrapporten: «Large claims affected our operations during the period.»',
        'companies':['Fremtind'],'sources':[{'company':'Fremtind','url':'https://reports.example.com/Fremtind.pdf','kind':'official_quarterly_report','page':3}]}
   (data/'quarterly_insights.json').write_text(json.dumps({'periods':{'Q1 2027':[raw]}}))
   with patch.object(build_editorial,'ROOT',Path(d)):
    output=build_editorial.build({'observations':[self.row('Fremtind')]},{'items':[]})
   text=' '.join(item['text'] for item in output['brief'])
   self.assertNotIn('omtaler i kvartalsrapporten',text)
   self.assertNotIn('Large claims affected',text)
   self.assertTrue(output['brief'])
 def test_legacy_excerpt_mislabeled_as_commentary_is_not_published(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';data.mkdir()
   legacy={'theme':'large_claims','basis':'issuer_commentary',
    'text':'Fremtind omtaler i kvartalsrapporten: «Large claims affected the quarter.»',
    'companies':['Fremtind'],'sources':[{'company':'Fremtind','url':'https://reports.example.com/fremtind.pdf','kind':'official_quarterly_report'}]}
   (data/'quarterly_insights.json').write_text(json.dumps({'periods':{'Q1 2027':[legacy]}}))
   with patch.object(build_editorial,'ROOT',Path(d)):
    result=build_editorial.build({'observations':[self.row('Fremtind')]},{'items':[]})
   self.assertTrue(result['brief'])
   self.assertTrue(all(' omtaler i kvartalsrapporten:' not in item['text'] for item in result['brief']))
 def test_unreported_company_is_not_attributed_commentary(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';data.mkdir()
   (data/'quarterly_insights.json').write_text(json.dumps({'periods':{'Q1 2027':[{'theme':'weather','text':'Tryg beskriver stormsituasjonen i rapporten.','companies':['Tryg'],'sources':[{'company':'Tryg','url':'https://reports.example.com/Tryg.pdf','kind':'official_quarterly_report'}]}]}}))
   with patch.object(build_editorial,'ROOT',Path(d)):
    result=build_editorial.build({'observations':[self.row('Fremtind')]},{'items':[]})
    self.assertNotIn('Tryg beskriver stormsituasjonen',' '.join(x['text'] for x in result['brief']))
if __name__=='__main__':unittest.main()
