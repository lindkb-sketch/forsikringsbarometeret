import unittest
from scripts.protector_2024_official_backfill import parse

class ProtectorHistoricalBackfillTests(unittest.TestCase):
 def test_official_income_overview_columns(self):
  page='Income overview\nNOKm Q3 2025 Q3 2024 Q1-Q3 2025 Q1-Q3 2024 FY 2024\nInsurance revenue 3,529 3,002 10,197 8,601 11,783'
  no,row=parse([(5,page)])
  self.assertEqual(no,5)
  self.assertEqual(row['2024_quarter'],3002)
  self.assertEqual(row['2024_ytd'],8601)
 def test_premium_row_is_not_revenue(self):
  with self.assertRaises(ValueError):
   parse([(5,'Income overview\nNOKm Q3 2025 Q3 2024 Q1-Q3 2025 Q1-Q3 2024 FY 2024\nGross written premium 1,676 1,664 11,165 9,645 12,333')])
 def test_ambiguous_duplicate_is_rejected(self):
  page='Income overview\nNOKm Q3 2025 Q3 2024 Q1-Q3 2025 Q1-Q3 2024 FY 2024\nInsurance revenue 3,529 3,002 10,197 8,601 11,783'
  with self.assertRaises(ValueError):parse([(5,page),(6,page)])
if __name__=='__main__':unittest.main()
