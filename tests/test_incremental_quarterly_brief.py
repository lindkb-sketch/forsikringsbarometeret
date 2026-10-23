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
 def test_unreported_company_is_not_attributed_commentary(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';data.mkdir()
   (data/'quarterly_insights.json').write_text(json.dumps({'periods':{'Q1 2027':[{'theme':'weather','text':'Tryg beskriver stormsituasjonen i rapporten.','companies':['Tryg'],'sources':[{'company':'Tryg','url':'https://reports.example.com/Tryg.pdf','kind':'official_quarterly_report'}]}]}}))
   with patch.object(build_editorial,'ROOT',Path(d)):
    result=build_editorial.build({'observations':[self.row('Fremtind')]},{'items':[]})
    self.assertNotIn('Tryg beskriver stormsituasjonen',' '.join(x['text'] for x in result['brief']))
if __name__=='__main__':unittest.main()
