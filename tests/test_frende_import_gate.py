import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import import_frende_holding as importer

class FrendeHoldingGateTests(unittest.TestCase):
    def test_discovery_is_not_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates.json"
            path.write_text(json.dumps({"complete": True, "candidates": [
                {"company": "Frende", "year": 2026, "quarter": 2,
                 "document_url": "https://frende.wrep.it/q2-2026-frende-holding-as"}]}))
            with patch.object(importer, "CANDIDATES", path):
                with self.assertRaisesRegex(RuntimeError, "not yet verified"):
                    importer.run()

    def test_incomplete_discovery_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates.json"
            path.write_text(json.dumps({"complete": False, "candidates": []}))
            with patch.object(importer, "CANDIDATES", path):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    importer.run()
