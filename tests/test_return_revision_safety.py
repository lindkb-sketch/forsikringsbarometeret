import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import import_reported_returns as returns


class ReturnRevisionSafetyTests(unittest.TestCase):
    def test_existing_record_is_rechecked_not_skipped(self):
        source = Path(returns.__file__).read_text(encoding="utf-8")
        self.assertNotIn("if k in existing:continue", source)
        self.assertIn("RETURN_OFFICIAL_PDF_REVISION", source)
        self.assertIn("source_revision_history", source)

    def test_parser_rejects_non_pdf(self):
        with self.assertRaises(ValueError):
            returns.extract(b"not a PDF", "Protector", 2026, 3)

    def test_no_unverified_source_overwrite(self):
        source = Path(returns.__file__).read_text(encoding="utf-8")
        self.assertIn("old.get('source_url')!=url", source)
        self.assertIn("RETURN_LEGACY_REVIEW_REQUIRED", source)


if __name__ == "__main__":
    unittest.main()
