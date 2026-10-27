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
  self.assertEqual(publishing,['update.yml'],publishing)

if __name__=='__main__': unittest.main()
