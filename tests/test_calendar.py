import importlib.util
import pathlib
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('monitor_update', ROOT / 'scripts/update.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class Tests(unittest.TestCase):
    def test_lock_requires_review_and_source(self):
        x = {'Tryg': {'Q3 2026': {'reviewed': False, 'locked_at': '2026-10-20', 'source_url': 'https://tryg.com'}}}
        self.assertFalse(mod.is_locked(x, 'Tryg', 'Q3 2026'))
        x['Tryg']['Q3 2026']['reviewed'] = True
        self.assertTrue(mod.is_locked(x, 'Tryg', 'Q3 2026'))
    def test_transition_to_q4(self):
        config = {'Storebrand': {'calendar_url': 'https://example.com', 'events': [{'period': 'Q3 2026', 'date': '2026-10-21'}, {'period': 'Q4 2026', 'date': '2027-02-10'}]}}
        locks = {'Storebrand': {'Q3 2026': {'reviewed': True, 'locked_at': '2026-10-22', 'source_url': 'https://example.com/report'}}}
        self.assertEqual(mod.build(config, locks)['companies']['Storebrand']['next_event']['period'], 'Q4 2026')
    def test_bad_date(self):
        with self.assertRaises(ValueError): mod.validate_events([{'period': 'Q4 2026', 'date': '2027-02-30'}])
