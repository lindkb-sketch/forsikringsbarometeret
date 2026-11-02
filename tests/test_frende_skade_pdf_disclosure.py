"""Prevent silent omission or conflation of Frende's separate non-life entity."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]

class FrendeSkadeDisclosure(unittest.TestCase):
    def test_separate_official_pdf_disclosure_is_rendered(self):
        script=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
        self.assertIn("if(c==='Frende')",script)
        self.assertIn('frende-skade-pdf-disclosure',script)
        self.assertIn('Frende Skadeforsikring AS – egne kvartalsrapporter',script)
        self.assertIn('data/frende_skade_reports.json',script)
        reports=json.loads((ROOT/'data/frende_skade_reports.json').read_text())['reports']
        self.assertTrue({(2026,1),(2026,2),(2026,3)} <= {(r['year'],r['quarter']) for r in reports})
    def test_holding_rows_not_relabelled_as_skade(self):
        observations=json.loads((ROOT/'data/financial_observations.json').read_text(encoding='utf-8'))['observations']
        holding=[r for r in observations if r.get('company')=='Frende']
        self.assertTrue(holding)
        self.assertTrue(all(r.get('source_entity')=='Frende Holding AS konsern' for r in holding))
if __name__=='__main__':unittest.main()
