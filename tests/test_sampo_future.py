#!/usr/bin/env python3
"""Future-quarter contract tests without pretending unreleased issuer reports exist."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sampo_publish as s

def overview(year,q):
 return f"""Interim Statement Q{q} {year}
Financial overview
Insurance revenue (incl. brokerage), net EURm 2363 2188
Underwriting result EURm 368 336
Risk ratio % 59.6 58.9
Cost ratio % 24.8 25.7
Combined ratio % 84.4 84.6
Nordic underlying development
"""
def segment(name):
 return f"""{name}
Insurance revenue, net EURm 1048 1010
Underwriting result EURm 179 160
Risk ratio % 61.6 60.0
Cost ratio % 21.4 23.0
Combined ratio % 83.0 83.0
"""
class Page:
 def __init__(self,text):self.text=text
 def extract_text(self):return self.text
class PDF:
 def __init__(self,pages):self.pages=[Page(p) for p in pages]
 def __enter__(self):return self
 def __exit__(self,*args):pass
class Tests(unittest.TestCase):
 def parse(self,year,q,header_q=None):
  pages=[overview(year,header_q or q),segment('Private Nordic'),segment('Nordic Commercial')]
  with patch.object(s.pdfplumber,'open',return_value=PDF(pages)):
   return s.parse(b'%PDF-synthetic','https://www.sampo.com/test.pdf',year,q)
 def test_q3_2026(self):
  rows=self.parse(2026,3)
  self.assertEqual(len(rows),15)
  self.assertEqual({r['segment'] for r in rows},{None,'Private Nordic','Nordic Commercial'})
  self.assertEqual({r['period_type'] for r in rows},{'quarter'})
  self.assertTrue(all(r['quarter']==3 and r['year']==2026 for r in rows))
 def test_q4_2026(self):
  self.assertEqual(len(self.parse(2026,4)),15)
 def test_q1_2027(self):
  self.assertEqual(len(self.parse(2027,1)),15)
 def test_wrong_quarter_rejected(self):
  with self.assertRaisesRegex(ValueError,'quarter'):
   self.parse(2026,3,header_q=2)
 def test_non_pdf_rejected(self):
  with self.assertRaisesRegex(ValueError,'PDF'):
   s.parse(b'not a report','https://www.sampo.com/test.pdf',2026,3)
if __name__=='__main__':unittest.main()
