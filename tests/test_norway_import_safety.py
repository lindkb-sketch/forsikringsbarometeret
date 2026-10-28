"""Regressions for Norway source completeness and fail-closed import."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class NorwayPipelineSafety(unittest.TestCase):
    def test_gjensidige_does_not_skip_missing_growth_or_result(self):
        content=(ROOT/"scripts/import_gjensidige_pdf_norway.py").read_text(encoding="utf-8")
        self.assertIn("required_segment_metrics=(*METRICS,'insurance_revenue_growth')",content)
        self.assertIn("for seg in SEGMENTS for m in required_segment_metrics",content)
        self.assertIn("'insurance_service_result'",content)

    def test_tryg_does_not_use_excel_to_hide_invalid_pdf_numbers(self):
        content=(ROOT/"scripts/import_tryg.py").read_text(encoding="utf-8")
        start=content.index("        try:\n            norway=parse_norway_pdf(pdf,year,quarter")
        stop=content.index("        previous={(r['period_type']",start)
        part=content[start:stop]
        self.assertLess(part.index("except ValueError as error:"),part.index("else:"))
        self.assertIn("existing,_=merge(existing,norway)",part[part.index("else:"):])
        self.assertNotIn("existing,_=merge(existing,norway)",part[:part.index("except ValueError as error:")])

if __name__=="__main__":
    unittest.main()
