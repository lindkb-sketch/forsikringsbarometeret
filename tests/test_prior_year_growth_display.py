"""Guard explicit prior-year revenue growth for current and future periods."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class PriorGrowthDisplayTests(unittest.TestCase):
 def test_growth_has_separate_current_and_previous_year_lines(self):
  js=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
  self.assertIn("const previousGrowth=d.growthPrev||'Ikke verifisert",js)
  self.assertIn('Fjorårets inntektsvekst: ',js)
  self.assertIn("const growthCell=tr.cells[2]",js)
  self.assertIn("+(year-2)",js)
  self.assertIn("const currentGrowth=d.growth||'Ikke verifisert'",js)
  self.assertIn("if(lastGrowth){",js)
  self.assertIn("data.growthPrev=fmt(lastGrowth.value,true)",js)

 def test_frende_future_pdf_cannot_be_skipped_silently(self):
  code=(ROOT/'scripts/import_frende_holding.py').read_text(encoding='utf-8')
  self.assertIn("Newer official Frende quarter discovered but not verified/imported",code)
  self.assertIn("all_periods and max(all_periods)>max(map(tuple,verified))",code)

if __name__=='__main__':
 unittest.main()
