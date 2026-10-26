import unittest
from scripts.storebrand_2024_official_backfill import parse

class StorebrandHistoricalRevenueTests(unittest.TestCase):
 def test_official_2025_q3_insurance_comparison_columns(self):
  page='Table 23: Insurance\nNOK million 2025 Q3 Q2 Q1 2024 Q4 Q3 01.01 - 30.09 2025 2024 2024\nInsurance premiums f.o.a. 2 475 2 408 2 256 2 134 2 044 7 140 5 874 8 008'
  idx,vals=parse([(32,page)])
  self.assertEqual(idx,32)
  self.assertEqual(vals[(2024,'quarter')],2044)
  self.assertEqual(vals[(2024,'ytd')],5874)
 def test_forsikring_as_not_mislabeled_group(self):
  with self.assertRaises(ValueError):parse([(65,'Table 57: Profit Storebrand Forsikring AS\nInsurance premiums f.o.a. 1 226 1 173 1 068 988 950 3 466 2 651 3 639')])
 def test_reject_duplicates(self):
  page='Table 23: Insurance\nInsurance premiums f.o.a. 2 475 2 408 2 256 2 134 2 044 7 140 5 874 8 008'
  with self.assertRaises(ValueError):parse([(28,page),(30,page)])

if __name__=='__main__':unittest.main()
