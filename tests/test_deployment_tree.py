"""Prevent partial GitHub Pages deployment and dropped generated reports."""
import tempfile
import unittest
from pathlib import Path
from scripts.verify_deployment_tree import ESSENTIAL, verify

ROOT=Path(__file__).resolve().parents[1]

class DeploymentTreeTests(unittest.TestCase):
 def test_real_checkout_has_publishable_assets(self):
  # Generated coverage JSON exists during workflow after ingestion; for this
  # checked-in tree use a disposable placeholder in an isolated copy.
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for item in ESSENTIAL:
    p=root/item
    p.parent.mkdir(parents=True,exist_ok=True)
    original=ROOT/item
    p.write_bytes(original.read_bytes() if original.is_file() else b'{}')
   (root/'index.html').write_text('<script src="scripts/financial_model.js"></script><script src="scripts/quarterly_runtime.js"></script>')
   self.assertEqual(verify(root)['required_assets'],len(ESSENTIAL))
   (root/'scripts/quarterly_runtime.js').unlink()
   with self.assertRaisesRegex(ValueError,'quarterly_runtime.js'):
    verify(root)
 def test_pipeline_packages_full_main_tree(self):
  workflow=(ROOT/'.github/workflows/update.yml').read_text()
  self.assertIn('git reset --hard origin/main',workflow)
  self.assertIn('path: .',workflow)
  self.assertIn('python scripts/verify_deployment_tree.py',workflow)
  self.assertLess(workflow.index('python scripts/verify_deployment_tree.py'),
                  workflow.index('actions/upload-pages-artifact@v3'))
  self.assertIn('node tests/live_browser_e2e.cjs',workflow)
  # The same generated audit is staged in both the initial and retry paths.
  self.assertGreaterEqual(workflow.count('data/profitability_coverage.json'),2)

if __name__=='__main__':unittest.main()
