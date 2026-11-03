"""No two GitHub Actions workflows may deploy to GitHub Pages concurrently."""
import re
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKFLOWS=ROOT/'.github'/'workflows'
GROUP='forsikringsbarometeret-publish'

class DeployConcurrencyTests(unittest.TestCase):
 def test_all_pages_publishers_share_one_concurrency_lock(self):
  publishing=[]
  for path in WORKFLOWS.glob('*.yml'):
   text=path.read_text(encoding='utf-8')
   if 'actions/deploy-pages@' not in text:
    continue
   publishing.append(path.name)
   self.assertRegex(text,r'(?m)^concurrency:\s*\n\s*group:\s*'+re.escape(GROUP)+r'\s*$')
   self.assertRegex(text,r'(?m)^\s*cancel-in-progress:\s*false\s*$')
  self.assertEqual(sorted(publishing),['stock-prices.yml','update.yml'],publishing)
  quote=(WORKFLOWS/'stock-prices.yml').read_text(encoding='utf-8')
  full=(WORKFLOWS/'update.yml').read_text(encoding='utf-8')
  # The lightweight job may only write verified stock JSON, never financial observations.
  self.assertIn('python scripts/verify_stock_feed.py',quote)
  self.assertIn('python scripts/verify_deployment_tree.py',quote)
  self.assertIn('python scripts/verify_public_stock_prices.py',quote)
  self.assertIn('if: steps.changes.outputs.changed',quote)
  self.assertNotIn('python scripts/run_pipeline.py',quote)
  self.assertIn('python scripts/run_pipeline.py',full)
  self.assertIn('python scripts/verify_public_pages.py',full)

if __name__=='__main__': unittest.main()
