import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ReviewedQuarterTests(unittest.TestCase):
 def test_source_reviewed_q3_summaries(self):
  d=json.loads((ROOT/'data/q3_2026_editorial_review.json').read_text())
  self.assertEqual(d['period'],'Q3 2026')
  self.assertEqual(d['status'],'source_reviewed')
  self.assertEqual(set(d['narratives']),{'Fremtind','Gjensidige','Tryg','Frende','Protector','Storebrand'})
  for company,entry in d['narratives'].items():
   with self.subTest(company=company):
    self.assertTrue(entry['verified'])
    self.assertEqual(entry['period'],d['period'])
    self.assertTrue(entry['source_url'].startswith('https://'))
    self.assertTrue(90<=len(entry['text'].split())<=150)
    self.assertEqual(len(entry['text'].split('\n\n')),2)
 def test_generated_feed_contains_reviewed_text(self):
  from scripts.build_editorial import build
  feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
  news=json.loads((ROOT/'data/official_news.json').read_text())
  result=build(feed,news)
  reviewed=json.loads((ROOT/'data/q3_2026_editorial_review.json').read_text())
  for company,entry in reviewed['narratives'].items():
   with self.subTest(company=company):
    actual=result['periods']['Q3 2026']['by_company'][company]['editorial_review']
    self.assertEqual(actual['text'],entry['text'])
    self.assertEqual(actual['source_url'],entry['source_url'])
