import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ingest_official_pdf import parse_highlights,merge
URL='https://www.gjensidige.com/report.pdf'
TEXT='''Group highlights
Second quarter
Group
Profit or loss before tax expense: NOK 2,789.6 million
General insurance
Insurance revenue: NOK 11,257.8 million (10,493.2)
Insurance service result: NOK 2,375.0 million (2,200.5)
Combined ratio: 78.9% (79.0%)
Cost ratio: 11.7% (12.0%)
Year-to-date
Group
Profit or loss before tax expense: NOK 4,844.4 million
General insurance
Insurance revenue: NOK 22,261.9 million (20,487.1)
Insurance service result: NOK 4,663.1 million (3,514.1)
Combined ratio: 79.1% (82.8%)
Cost ratio: 11.7% (12.0%)
'''
class PDFImportTests(unittest.TestCase):
 def test_quarter_and_reported_ytd(self):
  rows=parse_highlights([(2,TEXT)],'Gjensidige',2026,2,URL,'abc')
  self.assertEqual(len(rows),8)
  def v(p,m):return next(r['value'] for r in rows if r['period_type']==p and r['metric']==m)
  self.assertEqual(v('quarter','insurance_revenue'),11257.8)
  self.assertEqual(v('ytd','insurance_revenue'),22261.9)
  self.assertEqual(v('ytd','combined_ratio'),79.1)
 def test_other_company_not_guessed(self):
  self.assertEqual(parse_highlights([(2,TEXT)],'Frende',2026,2,URL,'abc'),[])
 def test_conflicting_existing_rejected(self):
  row=parse_highlights([(2,TEXT)],'Gjensidige',2026,2,URL,'abc')[0]
  with self.assertRaises(ValueError):merge({'observations':[{**row,'value':1}]},[row])
