import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from synthesize_report_commentary import synthesize
import build_editorial

class SynthesisTests(unittest.TestCase):
 def evidence(self,quote,theme='large_claims',company='Sampo',page=4):
  url='https://issuer.example.com/2027q1.pdf'
  return {'basis':'issuer_pdf_verbatim','theme':theme,
    'text':company+' omtaler i kvartalsrapporten: «'+quote+'»',
    'companies':[company],'sources':[{'company':company,'url':url,'page':page,
    'sha256':'a'*64,'kind':'official_quarterly_report'}]}
 def test_reliable_report_sentence_generates_norwegian_copy(self):
  item=synthesize(self.evidence('Furthermore, the first quarter saw fewer large claims than budgeted.'))
  self.assertIsNotNone(item)
  self.assertIn('storskader',item['text'])
  self.assertEqual(item['sources'][0]['page'],4)
  self.assertNotIn('omtaler i kvartalsrapporten',item['text'])
 def test_garbled_or_unsupported_cannot_be_published(self):
  self.assertIsNone(synthesize(self.evidence('Insurance revenue in Denmark increased by insurance. Favourable weather conditions competitive cost base.','weather')))
  self.assertIsNone(synthesize(self.evidence('An unusual incident happened and had a major financial effect.')))
  self.assertIsNone(synthesize(self.evidence('Furthermore, the first quarter saw fewer large claims than budgeted.',page=None)))
 def test_realistic_future_issuer_arrival_updates_brief(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'data').mkdir()
   row=self.evidence('Furthermore, the first quarter saw fewer large claims than budgeted.')
   (root/'data/quarterly_insights.json').write_text(json.dumps({'periods':{'Q1 2027':[row]}}))
   financial={'observations':[{'company':'Sampo','year':2027,'quarter':1,
    'scope':'group','period_type':'quarter','metric':'combined_ratio','unit':'percent',
    'value':80,'status':'reported','source_url':'https://issuer.example.com/2027q1.pdf'}]}
   with patch.object(build_editorial,'ROOT',root):
    out=build_editorial.build(financial,{'items':[]})
   self.assertEqual(out['period'],'Q1 2027')
   self.assertIn('Sampo',out['brief'][0]['text'])
   self.assertEqual(out['brief'][0]['basis'],'rule_verified_issuer_narrative')
   self.assertLessEqual(sum(len(x['text'].split()) for x in out['brief']),220)
if __name__=='__main__':unittest.main()
