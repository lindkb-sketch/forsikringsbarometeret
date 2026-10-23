"""Issuer report comparative columns must be imported as verified Q/YTD prior-year observations."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_tryg import parse_group

class Page:
 def __init__(self,text):self.text=text
 def extract_text(self):return self.text
class PDF:
 def __init__(self,text):self.pages=[Page(text)]
 def __enter__(self):return self
 def __exit__(self,*args):return False

class TrygComparativesTests(unittest.TestCase):
 def test_q3_comparison_columns_for_2025_and_2026(self):
  lines=[
   'Income overview',
   'Q3 Q1-Q3',
   '2026 2025 2026 2025 2025',
   'Insurance revenue 10591 9900 31563 29000 41000',
   'Insurance service result 2500 2400 5200 5000 7000',
   'Claims ratio, net of reinsurance 63.6 65.5 69.9 69.0 67.0',
   'Expense ratio 13.3 13.0 13.3 13.0 13.3',
   'Combined ratio 76.8 78.5 83.2 82.0 80.3',
  ]
  with patch('import_tryg.pdfplumber.open',return_value=PDF('\n'.join(lines))):
   records=parse_group(b'%PDF-test',2026,3,'https://tryg.com/q3-2026.pdf')
  values={(r['year'],r['period_type'],r['metric']):r['value'] for r in records}
  self.assertEqual(len(records),20)
  self.assertEqual(values[(2025,'quarter','insurance_revenue')],9900)
  self.assertEqual(values[(2025,'ytd','insurance_revenue')],29000)
  self.assertEqual(values[(2025,'quarter','combined_ratio')],78.5)
  self.assertEqual(values[(2026,'quarter','combined_ratio')],76.8)
  self.assertTrue(all(r['source_document_period']=='Q3 2026' for r in records))

 def test_q1_comparison_columns_are_ytd_too(self):
  lines=[
   'Income overview','Q1','2027 2026 2026',
   'Insurance revenue 12100 11000 43000',
   'Insurance service result 900 800 3000',
   'Claims ratio, net of reinsurance 64.0 65.0 64.0',
   'Expense ratio 13.0 13.0 13.0',
   'Combined ratio 77.0 78.0 77.0',
  ]
  with patch('import_tryg.pdfplumber.open',return_value=PDF('\n'.join(lines))):
   records=parse_group(b'%PDF-test',2027,1,'https://tryg.com/q1-2027.pdf')
  self.assertEqual(len(records),20)
  self.assertEqual(next(r['value'] for r in records if r['year']==2026 and r['period_type']=='ytd' and r['metric']=='insurance_revenue'),11000)

if __name__=='__main__':unittest.main()
