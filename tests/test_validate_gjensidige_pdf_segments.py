"""Offline checks for the read-only official PDF validation workflow."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_gjensidige_pdf_segments as validator


class GjensidigePdfValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "financial_observations.json"
        self.rows = [{
            "company": "Gjensidige", "scope": "group", "period_type": "quarter",
            "metric": "combined_ratio", "source_type": "official_quarterly_report",
            "source_url": "https://example.org/official-report.pdf",
            "year": 2026, "quarter": 3
        }]
        self.data.write_text(json.dumps({"observations": self.rows}), encoding="utf-8")

    def test_validates_both_norway_segments_from_pdf(self):
        parsed = [
            {"year": 2026, "quarter": 3, "segment": segment,
             "metric": metric, "source_page": page}
            for page, segment in enumerate(validator.SEGMENTS, 5)
            for metric in validator.METRICS
        ]
        with patch.object(validator, "DATA", self.data), \
             patch.object(validator, "download", return_value=b"%PDF-test"), \
             patch.object(validator, "read_pdf", return_value=[(5, "private"), (6, "commercial")]), \
             patch.object(validator, "parse", return_value=parsed) as parse:
            result = validator.validate()
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["segments"], list(validator.SEGMENTS))
        self.assertEqual(result["source_pages"], [5, 6])
        parse.assert_called_once()

    def test_rejects_missing_segment_metric(self):
        parsed = [
            {"year": 2026, "quarter": 3, "segment": segment,
             "metric": metric, "source_page": 5}
            for segment in validator.SEGMENTS
            for metric in validator.METRICS
            if not (segment == "Commercial Norway" and metric == "combined_ratio")
        ]
        with patch.object(validator, "DATA", self.data), \
             patch.object(validator, "download", return_value=b"%PDF-test"), \
             patch.object(validator, "read_pdf", return_value=[]), \
             patch.object(validator, "parse", return_value=parsed):
            with self.assertRaisesRegex(ValueError, "missing PDF metrics"):
                validator.validate()

    def test_rejects_non_pdf(self):
        with patch.object(validator, "DATA", self.data), \
             patch.object(validator, "download", return_value=b"not a pdf"):
            with self.assertRaisesRegex(ValueError, "not a PDF"):
                validator.validate()


if __name__ == "__main__":
    unittest.main()
