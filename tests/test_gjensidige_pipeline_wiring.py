"""Regression checks: scheduled deployment must run Gjensidige Norway import."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class GjensidigeNorwayPipelineTest(unittest.TestCase):
    def test_main_pipeline_imports_pdf_before_feed_build(self):
        script=(ROOT/"scripts/run_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("'import_gjensidige_latest.py'",script)
        self.assertIn("'import_gjensidige_pdf_norway.py'",script)
        self.assertLess(script.index("'import_gjensidige_latest.py'"),
                        script.index("'import_gjensidige_pdf_norway.py'"))
        self.assertLess(script.index("'import_gjensidige_pdf_norway.py'"),
                        script.index("'build_verified_feed.py'"))

    def test_scheduled_workflow_enforces_contract_before_deploy(self):
        script=(ROOT/".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn("schedule:",script)
        self.assertIn("python scripts/run_pipeline.py",script)
        self.assertIn("python scripts/quarterly_import_contract.py",script)
        self.assertLess(script.index("python scripts/quarterly_import_contract.py"),
                        script.index("actions/deploy-pages@v4"))

if __name__=="__main__":
    unittest.main()
