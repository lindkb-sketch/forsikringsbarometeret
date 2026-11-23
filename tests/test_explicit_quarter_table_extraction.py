import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from reconcile_nine_pdf_metrics import extract_explicit_quarter_column

class ExplicitQuarterColumnTests(unittest.TestCase):
 def test_current_q3_value_with_prior_comparator(self):
  lines=['Metric    Q3 2026    Q3 2025','Combined ratio    89.2    91.3']
  self.assertEqual(extract_explicit_quarter_column(lines,'combined_ratio',2026,3),89.2)
 def test_reversed_year_columns(self):
  lines=['Metric    Q3 2025    Q3 2026','Combined ratio    91.3    89.2']
  self.assertEqual(extract_explicit_quarter_column(lines,'combined_ratio',2026,3),89.2)
 def test_no_target_quarter_header(self):
  self.assertIsNone(extract_explicit_quarter_column(['Metric    Q3 2025    Q2 2026','Combined ratio    91.3    89.2'],'combined_ratio',2026,3))
 def test_ambiguous_duplicate_headers(self):
  self.assertIsNone(extract_explicit_quarter_column(['Metric    Q3 2026    Q3 2026','Combined ratio    89.2    91.3'],'combined_ratio',2026,3))
 def test_no_guess_from_single_value(self):
  self.assertIsNone(extract_explicit_quarter_column(['Combined ratio 89.2'],'combined_ratio',2026,3))
if __name__=='__main__':unittest.main()
