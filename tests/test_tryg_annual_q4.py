"""Tryg publishes Q4 together with annual/full-year reporting.

Discover it as Q4 ONLY when the official archive has both the annual PDF
and the matching Q4 investor workbook. No calendar date is a result source.
"""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from discover_tryg import parse
from import_tryg import parse_group

class TrygAnnualQ4(unittest.TestCase):
 def test_annual_pdf_and_q4_workbook_become_one_q4_pair(self):
  markup='''<a href="/media/annual_report_2027.pdf">Annual Report 2027</a>
  <a href="/media/tryg-group-q4-2027-investor-tables.xlsx">Tryg Group - Q4 2027 - Investor tables</a>
  <a href="/media/presentation_q4_2027.pdf">Q4 2027 investor presentation</a>'''
  rows=parse(markup,2027)
  self.assertEqual(len(rows),1)
  self.assertEqual((rows[0]['year'],rows[0]['quarter']),(2027,4))
  self.assertIn('annual_report_2027.pdf',rows[0]['report_pdf_url'])
  self.assertNotIn('workbook_url',rows[0])
 def test_annual_pdf_is_sufficient_for_discovery(self):
  self.assertEqual(len(parse('<a href="/annual_report_2027.pdf">Annual Report 2027</a>',2027)),1)
 def test_q4_workbook_only_is_not_marked_as_published(self):
  self.assertEqual(parse('<a href="/tryg-q4-2027-investor-tables.xlsx">Q4 2027 investor tables</a>',2027),[])
 def test_wrong_year_does_not_match(self):
  markup='<a href="/annual_report_2026.pdf">Annual Report 2026</a><a href="/q4-2026-investor-tables.xlsx">Q4 2026 investor tables</a>'
  self.assertEqual(parse(markup,2027),[])
 def test_pdf_parser_rejects_non_pdf_without_creating_q4_observations(self):
  with self.assertRaises(ValueError):
   parse_group(b'not a pdf',2027,4,'https://tryg.com/annual-report.pdf')
if __name__=='__main__':unittest.main()
