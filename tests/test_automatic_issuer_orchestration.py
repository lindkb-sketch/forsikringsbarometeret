"""Structural regression tests for the seven automatic report ingestion paths.

This proves the scheduled wiring exists, not that a new issuer PDF is parsed.
Financial completion is tracked separately in data/report_coverage.json.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / ".github/workflows/update.yml").read_text()
PIPELINE = (ROOT / "scripts/run_pipeline.py").read_text()

class AutomaticIssuerOrchestrationTests(unittest.TestCase):
    def test_all_seven_have_a_scheduled_ingestion_path(self):
        dedicated = {
            "Gjensidige": (".github/workflows/gjensidige-publish.yml", "scripts/gjensidige_publish.py"),
            "Sampo": (".github/workflows/sampo-publish.yml", "scripts/sampo_publish.py"),
            "Protector": (".github/workflows/protector-verify.yml", "scripts/protector_publish.py"),
            "Storebrand": (".github/workflows/storebrand-auto-q3.yml", "scripts/storebrand_publish_q3.py"),
        }
        for company, (workflow, importer) in dedicated.items():
            with self.subTest(company=company):
                spec = (ROOT / workflow).read_text()
                self.assertIn("schedule:", spec)
                self.assertIn(importer, spec)
                self.assertIn("group: forsikringsbarometeret-publish", spec)
        for company, importer in {
            "Fremtind": "import_fremtind_holding.py",
            "Frende": "import_frende_holding.py",
            "Tryg": "import_tryg.py",
        }.items():
            with self.subTest(company=company):
                self.assertIn(importer, PIPELINE)
        self.assertIn("schedule:", MAIN)
        self.assertIn("scripts/run_pipeline.py", MAIN)

    def test_source_registry_includes_all_seven(self):
        import json
        rows = json.loads((ROOT / "data/report_sources.json").read_text())["sources"]
        expected = {"Fremtind", "Gjensidige", "Tryg", "Sampo", "Frende", "Protector", "Storebrand"}
        self.assertEqual(expected, {row["company"] for row in rows})

    def test_coverage_is_not_confused_with_workflow_success(self):
        import json
        coverage = json.loads((ROOT / "data/report_coverage.json").read_text())
        self.assertEqual(len(coverage["companies"]), 7)
        self.assertEqual(coverage["all_seven_automatic"],
                         all(item["automatic_complete"] for item in coverage["companies"]))

if __name__ == "__main__":
    unittest.main()
