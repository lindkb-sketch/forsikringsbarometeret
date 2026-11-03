"""Frende Skade numbers belong in the existing Norway business segment row."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class FrendeSkadeLayoutTests(unittest.TestCase):
    def test_existing_norway_row_populated_without_duplicate_table(self):
        js=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
        self.assertIn("if(c==='Frende')",js)
        self.assertIn("Frende Skadeforsikring AS",js)
        self.assertIn("frende-skade-verified-row",js)
        self.assertIn("segmentRow.cells[i+1]",js)
        self.assertIn("insurance_service_result",js)
        self.assertIn("combined_ratio",js)
        self.assertIn("loss_ratio",js)
        self.assertIn("expense_ratio",js)
        self.assertNotIn("frende-skade-pdf-disclosure",js)
    def test_source_link_is_compact_and_responsive(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        self.assertIn(".frende-skade-source",html)
        self.assertIn(".frende-skade-verified-row",html)
if __name__=='__main__':unittest.main()
