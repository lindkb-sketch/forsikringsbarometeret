import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_editorial import build
class EditorialTests(unittest.TestCase):
 def test_unapproved_news_not_published(self):
  feed={'observations':[{'company':'Tryg','year':2026,'quarter':3,'scope':'norway','period_type':'quarter','metric':'combined_ratio','value':76.1,'source_url':'https://example.org/report.pdf'}]}
  result=build(feed,{'items':[{'headline':'Unverified','source_url':'https://example.org','published_at':'2026-10-01'}]})
  self.assertEqual(result['news'],[]);self.assertEqual(len(result['implications']),0)
 def test_apm_premiums_not_mislabeled_as_ifrs_revenue(self):
  feed={'observations':[{'company':'Storebrand','year':2026,'quarter':3,
    'scope':'group','period_type':'quarter','metric':'insurance_revenue',
    'value':2896,'unit':'MNOK','source_url':'https://example.org/storebrand.pdf',
    'source_definition':'APM: Insurance segment premiums f.o.a.; not IFRS insurance revenue'}]}
  text=build(feed,{'items':[]})['brief'][0]['text']
  self.assertIn('segmentpremier (APM, ikke IFRS-forsikringsinntekter)',text)
  self.assertNotIn(': forsikringsinntekter 2896',text)
 def test_group_quarterly_commentary_compares_last_reported_quarter(self):
  feed={'observations':[
    {'company':'Fremtind','year':2026,'quarter':2,'scope':'group','period_type':'quarter',
     'metric':'combined_ratio','value':77.5,'status':'reported','source_url':'https://example.org/q2.pdf'},
    {'company':'Fremtind','year':2026,'quarter':3,'scope':'group','period_type':'quarter',
     'metric':'combined_ratio','value':73.0,'status':'reported','source_url':'https://example.org/q3.pdf'}]}
  text=build(feed,{'items':[]})['implications'][0]['text']
  self.assertIn('forbedret',text)
  self.assertIn('4.5 prosentpoeng',text)
  self.assertIn('Q2 2026',text)
 def test_no_data(self):self.assertEqual(build({'observations':[]},{'items':[]})['coverage'],'no_verified_data')
