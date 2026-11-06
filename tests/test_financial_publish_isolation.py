"""Integration tests: a validated finance snapshot must never overwrite quotes."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from publish_prepared_financial import FILES, REQUIRED, STAGE, prepare, publish


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(f'git {args!r} failed: {result.stderr}')
    return result.stdout.strip()


class FinancePublishIsolationTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.bare = self.root / 'origin.git'
        self.initial = self.root / 'prepare'
        git(self.root, 'init', '--bare', '--initial-branch=main', str(self.bare))
        git(self.root, 'init', '--initial-branch=main', str(self.initial))
        git(self.initial, 'config', 'user.name', 'CI test')
        git(self.initial, 'config', 'user.email', 'test@example.invalid')
        (self.initial / 'index.html').write_text('original html')
        (self.initial / 'data').mkdir()
        (self.initial / 'data' / 'stock_prices.json').write_text('{"close":100}\n')
        for rel in REQUIRED:
            p = self.initial / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{"quarter":"Q3","value":50}\n')
        git(self.initial, 'add', '.')
        git(self.initial, 'commit', '-m', 'baseline')
        git(self.initial, 'remote', 'add', 'origin', str(self.bare))
        git(self.initial, 'push', '-u', 'origin', 'main')

    def change_main(self, path, data):
        other = self.root / 'newer'
        git(self.root, 'clone', '-b', 'main', str(self.bare), str(other))
        git(other, 'config', 'user.name', 'External change')
        git(other, 'config', 'user.email', 'other@example.invalid')
        (other / path).write_text(data)
        git(other, 'add', path)
        git(other, 'commit', '-m', 'other update')
        git(other, 'push', 'origin', 'HEAD:main')

    def publish_snapshot(self):
        current = self.root / 'publish'
        git(self.root, 'clone', '-b', 'main', str(self.bare), str(current))
        shutil.copytree(self.initial / STAGE, current / STAGE)
        return current

    def test_stock_advances_during_finance_validation_without_being_overwritten(self):
        (self.initial / 'data' / 'verified_financial_feed.json').write_text('{"value":51}\n')
        prepare(self.initial)
        self.change_main('data/stock_prices.json', '{"close":110}\n')
        current = self.publish_snapshot()
        publish(current)
        self.assertEqual(json.loads((current / 'data/stock_prices.json').read_text())['close'], 110)
        self.assertEqual(json.loads((current / 'data/verified_financial_feed.json').read_text())['value'], 51)
        self.assertNotIn('stock_prices.json', git(current, 'show', '--format=', '--name-only', 'HEAD'))
        self.assertIn('verified_financial_feed.json', git(current, 'show', '--format=', '--name-only', 'HEAD'))
        self.assertNotIn('data/stock_prices.json', FILES)

    def test_code_changes_during_long_validation_are_rejected(self):
        (self.initial / 'data' / 'verified_financial_feed.json').write_text('{"value":51}\n')
        prepare(self.initial)
        self.change_main('index.html', 'new html')
        current = self.publish_snapshot()
        with self.assertRaisesRegex(ValueError, 'outside stock prices'):
            publish(current)
        self.assertEqual((current / 'index.html').read_text(), 'new html')

    def test_new_financial_data_from_another_job_cannot_be_replaced(self):
        (self.initial / 'data' / 'verified_financial_feed.json').write_text('{"value":51}\n')
        prepare(self.initial)
        self.change_main('data/verified_financial_feed.json', '{"value":52}\n')
        current = self.publish_snapshot()
        with self.assertRaisesRegex(ValueError, 'outside stock prices'):
            publish(current)
        self.assertEqual(json.loads((current / 'data/verified_financial_feed.json').read_text())['value'], 52)

    def test_modified_artifact_is_rejected_before_touching_files(self):
        prepare(self.initial)
        current = self.publish_snapshot()
        (current / STAGE / 'data' / 'financial_audit.json').write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            publish(current)

    def test_noop_finance_publishing_leaves_newer_stock_commit_untouched(self):
        prepare(self.initial)
        self.change_main('data/stock_prices.json', '{"close":109}\n')
        current = self.publish_snapshot()
        before = git(current, 'rev-parse', 'HEAD')
        publish(current)
        self.assertEqual(before, git(current, 'rev-parse', 'HEAD'))
        self.assertEqual(json.loads((current / 'data/stock_prices.json').read_text())['close'], 109)


if __name__ == '__main__':
    unittest.main()
