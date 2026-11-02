"""Ensure the Pages deployment tree rejects missing referenced scripts."""
import tempfile
import unittest
from pathlib import Path
from scripts.verify_deployment_tree import ESSENTIAL, verify


class DeploymentScriptAssetsTest(unittest.TestCase):
    def test_missing_local_script_blocks_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in ESSENTIAL:
                file = root / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('placeholder', encoding='utf-8')
            (root / 'index.html').write_text(
                '<script src="scripts/missing.js"></script>', encoding='utf-8'
            )
            with self.assertRaisesRegex(ValueError, 'scripts/missing.js'):
                verify(root)

    def test_present_script_is_counted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in ESSENTIAL:
                file = root / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('placeholder', encoding='utf-8')
            (root / 'index.html').write_text(
                '<script src="scripts/financial_model.js"></script>', encoding='utf-8'
            )
            self.assertEqual(verify(root)['scripts_validated'], 1)


if __name__ == '__main__':
    unittest.main()
