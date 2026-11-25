"""Wait for Pages artifact visibility before invoking deploy-pages."""
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pages_gate', ROOT / 'scripts/wait_pages_artifact.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PagesArtifactVisibilityTests(unittest.TestCase):
    def test_only_exact_unexpired_artifact_matches(self):
        self.assertFalse(module.artifact_is_visible({'artifacts': [{'name': 'github-pages-2'}]}))
        self.assertFalse(module.artifact_is_visible({'artifacts': [{'name': 'github-pages', 'expired': True}]}))
        self.assertTrue(module.artifact_is_visible({'artifacts': [{'name': 'github-pages', 'expired': False}]}))

    def test_retries_until_api_indexes_upload(self):
        calls = []
        payloads = iter(({'artifacts': []}, {'artifacts': [{'name': 'github-pages'}]}))
        class Context:
            def __init__(self, payload):
                self.stream = io.BytesIO(json.dumps(payload).encode())
            def __enter__(self):
                return self.stream
            def __exit__(self, *args):
                return False
        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            return Context(next(payloads))
        self.assertTrue(module.wait_for_artifact('owner/repo', '123', 'token', attempts=2, delay_seconds=0, sleep=lambda _: None, opener=opener))
        self.assertEqual(len(calls), 2)
        self.assertIn('/actions/runs/123/artifacts?', calls[0][0])

    def test_missing_or_never_visible_fails_closed(self):
        with self.assertRaises(ValueError):
            module.wait_for_artifact('owner/repo', '123', '')
        def opener(request, timeout):
            class Context:
                def __enter__(self):
                    return io.BytesIO(b'{"artifacts":[]}')
                def __exit__(self, *args):
                    return False
            return Context()
        with self.assertRaises(TimeoutError):
            module.wait_for_artifact('owner/repo', '123', 'token', attempts=2, delay_seconds=0, sleep=lambda _: None, opener=opener)

    def test_both_publishers_wait_on_visibility(self):
        for name in ('update.yml', 'stock-prices.yml'):
            source = (ROOT / '.github/workflows' / name).read_text(encoding='utf-8')
            self.assertIn('python scripts/wait_pages_artifact.py', source)
            self.assertLess(source.index('python scripts/wait_pages_artifact.py'), source.index('actions/deploy-pages@v4'))


if __name__ == '__main__':
    unittest.main()
