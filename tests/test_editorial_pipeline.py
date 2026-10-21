import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_editorial import build
class EditorialTests(unittest.TestCase):
 def test_unapproved_news_not_published(self):
  feed={'observations':[{'company':'Tryg','year':2026,'quarter':3,'scope':'norway','period_type':'quarter','metric':'combined_ratio','value':76.1,'source_url':'https://example.org/report.pdf'}]}
  result=build(feed,{'items':[{'headline':'Unverified','source_url':'https://example.org','published_at':'2026-10-01'}]})
  self.assertEqual(result['news'],[]);self.assertEqual(len(result['implications']),1)
 def test_no_data(self):self.assertEqual(build({'observations':[]},{'items':[]})['coverage'],'no_verified_data')
