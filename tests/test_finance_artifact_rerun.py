"""Publishing must find the prepared finance artifact after rerunning failed jobs."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class FinanceArtifactRerunTests(unittest.TestCase):
 def test_name_stable_between_attempts(self):
  workflow=(ROOT/'.github/workflows/update.yml').read_text(encoding='utf-8')
  name='verified-financial-\u0024{{ github.run_id }}'
  self.assertEqual(workflow.count('name: '+name),2)
  self.assertNotIn('verified-financial-\u0024{{ github.run_id }}-\u0024{{ github.run_attempt }}',workflow)
 def test_upload_overwrite_on_full_retry(self):
  workflow=(ROOT/'.github/workflows/update.yml').read_text(encoding='utf-8')
  upload=workflow.split('name: verified-financial-\u0024{{ github.run_id }}',1)[1]
  self.assertIn('overwrite: true',upload.split('  publish:',1)[0])
if __name__=='__main__':unittest.main()
