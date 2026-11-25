"""Only publishing, not expensive PDF validation, holds the shared Pages lock."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'
GROUP = 'forsikringsbarometeret-publish'


class DeployConcurrencyTests(unittest.TestCase):
    def test_all_pages_publishers_share_one_concurrency_lock(self):
        publishing = []
        for path in WORKFLOWS.glob('*.yml'):
            source = path.read_text(encoding='utf-8')
            if 'actions/deploy-pages@' not in source:
                continue
            publishing.append(path.name)
            if path.name == 'update.yml':
                # Only the short finance publish job may block stock jobs.
                self.assertNotRegex(source, r'(?m)^concurrency:')
                self.assertIn('  validate-and-prepare:', source)
                self.assertIn('  publish:\n    needs: validate-and-prepare', source)
                self.assertLess(source.index('python scripts/run_pipeline.py'), source.index('  publish:'))
                publish_job = source.split('  publish:', 1)[1]
                self.assertRegex(publish_job, r'(?m)^    concurrency:\s*\n      group: ' + re.escape(GROUP))
                self.assertIn('      queue: max', publish_job)
                self.assertIn('      cancel-in-progress: false', publish_job)
                self.assertIn('python scripts/publish_prepared_financial.py prepare', source)
                self.assertIn('python scripts/publish_prepared_financial.py publish', publish_job)
                self.assertIn('actions/download-artifact@v4', publish_job)
            else:
                self.assertRegex(source, r'(?m)^concurrency:\s*\n  group: ' + re.escape(GROUP))
                self.assertRegex(source, r'(?m)^  cancel-in-progress: false\s*$')
        self.assertEqual(sorted(publishing), ['stock-prices.yml', 'update.yml'], publishing)

        quote = (WORKFLOWS / 'stock-prices.yml').read_text(encoding='utf-8')
        full = (WORKFLOWS / 'update.yml').read_text(encoding='utf-8')
        script = (ROOT / 'scripts' / 'publish_prepared_financial.py').read_text(encoding='utf-8')
        self.assertIn('python scripts/verify_stock_feed.py', quote)
        self.assertIn('python scripts/verify_deployment_tree.py', quote)
        self.assertIn('python scripts/verify_public_stock_prices.py', quote)
        self.assertIn('if: steps.changes.outputs.changed', quote)
        self.assertNotIn('python scripts/run_pipeline.py', quote)
        self.assertIn('python scripts/run_pipeline.py', full)
        self.assertIn('python scripts/verify_public_pages.py', full)
        self.assertIn("'data/stock_prices.json', 'data/broker_commentary.json', 'data/official_news.json'", script)
        self.assertIn('FINANCIAL_PUBLISH_REBASE stock/broker/news changes retained', script)

    def test_stock_deployer_can_read_actions_artifacts(self):
        source = (WORKFLOWS / 'stock-prices.yml').read_text(encoding='utf-8')
        permissions = source.split('permissions:', 1)[1].split('jobs:', 1)[0]
        self.assertRegex(permissions, r'(?m)^  actions: read\\b')

    def test_pages_artifact_uses_github_required_name(self):
        # deploy-pages queries the artifact API using a Pages-specific lookup.
        # Custom artifact names upload successfully but fail deployment.
        for filename in ('update.yml', 'stock-prices.yml'):
            source = (WORKFLOWS / filename).read_text(encoding='utf-8')
            self.assertIn('name: github-pages\n', source)
            self.assertIn('artifact_name: github-pages\n', source)
            self.assertNotIn('github-pages-${{', source)
            self.assertNotIn('github-pages-stocks-', source)

    def test_finance_publisher_has_pages_environment(self):
        source = (WORKFLOWS / 'update.yml').read_text(encoding='utf-8')
        publisher = source.split('  publish:', 1)[1]
        self.assertIn('    environment:\n      name: github-pages\n', publisher)
        self.assertIn('url: ${{ steps.deployment.outputs.page_url }}', publisher)


if __name__ == '__main__':
    unittest.main()
