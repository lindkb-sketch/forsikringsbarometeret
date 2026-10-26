import unittest
from scripts.storebrand_2024_backfill import parse_pages

class StorebrandSourceComparatives(unittest.TestCase):
 def test_2025_supplement_table_23_2024_q3_and_ytd(self):
    pages=[(33,'Table 23: Insurance\nNOK million 2025 Q3 Q2 Q1 2024 Q4 Q3 01.01-30.09 2025 2024 FY2024\nInsurance premiums f.o.a. 2 475 2 408 2 256 2 134 2 044 7 140 5 874 8 008')]
    page,values=parse_pages(pages)
    self.assertEqual(page,33)
    self.assertEqual(values[('quarter',2024)],2044)
    self.assertEqual(values[('ytd',2024)],5874)
 def test_wrong_segment_and_2025_reference_rejected(self):
    with self.assertRaises(ValueError):
      parse_pages([(6,'Table 57: Storebrand Forsikring AS\nInsurance premiums f.o.a. 1 226 1 173 1 068 988 950 3 466 2 651 3 639')])
 def test_ambiguous_duplicate_rows_rejected(self):
    text='Table 23: Insurance\nInsurance premiums f.o.a. 2 475 2 408 2 256 2 134 2 044 7 140 5 874 8 008'
    with self.assertRaises(ValueError):parse_pages([(30,text),(31,text)])

if __name__=='__main__': unittest.main()
