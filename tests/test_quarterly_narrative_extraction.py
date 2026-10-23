import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from refresh_report_commentary import candidates,extract,TOPICS

class QuarterlyNarrativeExtractionTests(unittest.TestCase):
 def test_backfill_starts_at_2026(self):
  source=(ROOT/'scripts/refresh_report_commentary.py').read_text()
  self.assertIn("if x['year']<2026:continue",source)
 def test_official_prose_extraction_from_report_text(self):
  text=("Several large claims affected the underwriting performance during the quarter.\n"
        "The company reported weather-related claims after severe storm activity across its home market.\n"
        "Price increases contributed to organic growth during the reporting period.\n")
  rows=dict(candidates(text))
  self.assertIn('large_claims',rows)
  self.assertIn('weather',rows)
  self.assertIn('growth',rows)
 def test_no_unsubstantiated_events_from_financial_table(self):
  text="Large claims 2026 Q3 345 290 210\nCombined ratio 78.5 % | Gross profit 11.5\n"
  self.assertEqual(list(candidates(text)),[])
 def test_prose_requires_complete_non_numeric_sentence(self):
  text="Weather\nLarge claims are discussed as a topic\n"
  self.assertEqual(list(candidates(text)),[])
if __name__=='__main__':unittest.main()
