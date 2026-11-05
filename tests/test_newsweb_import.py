"""Offline contract tests. Synthetic messages never enter the production feed."""
import copy
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('newsweb', ROOT / 'scripts/update_newsweb_notices.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
NOW = dt.datetime(2026, 11, 5, 12, tzinfo=dt.timezone.utc)


class Provider:
    def __init__(self):
        self.details = {}
        self.rows = {}
        self.calls = []
        self.fail = False
        for index, (company, (seed, name)) in enumerate(mod.ISSUERS.items()):
            issuer = 11217 if company == 'Gjensidige' else 100 + index
            sign = 'GJF' if company == 'Gjensidige' else 'TEST' + str(index)
            template = {'issuerId': issuer, 'issuerSign': sign, 'issuerName': name,
                        'title': 'Synthetic test message', 'publishedTime': '2026-11-04T10:00:00Z'}
            self.details[seed] = {**template, 'messageId': seed}
            latest = {**template, 'messageId': 900000 + index}
            self.details[latest['messageId']] = latest
            self.rows[issuer] = [latest]

    def __call__(self, endpoint, params):
        self.calls.append((endpoint, params.copy()))
        if self.fail:
            raise OSError('simulated network outage')
        if endpoint == 'message':
            return {'data': {'message': copy.deepcopy(self.details[int(params['messageId'])])}}
        return {'data': {'messages': copy.deepcopy(self.rows[int(params['issuer'])]), 'overflow': False}}


class NewsWebImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'data/newsweb_notices.json'
        self.provider = Provider()
        self.client = mod.Client(self.provider)
        self.identity = self.client.identity('Gjensidige')

    def run_update(self, **kwargs):
        return mod.update(self.provider, now=kwargs.pop('now', NOW), out=self.path, **kwargs)

    def row(self, **overrides):
        row = self.provider.rows[11217][0].copy()
        row.update(overrides)
        return row

    def test_actual_update_writes_and_reads_json_for_six_verified_issuers(self):
        data = self.run_update(strict=True)
        self.assertEqual(data, json.loads(self.path.read_text()))
        self.assertEqual(set(data['notices']), set(mod.COMPANIES))
        self.assertEqual(sum(map(len, data['notices'].values())), 6)
        self.assertEqual(data['errors'], {})

    def test_uses_numeric_ids_and_json_api_not_html(self):
        self.run_update(strict=True)
        lists = [p for e, p in self.provider.calls if e == 'list']
        self.assertTrue(all(isinstance(p['issuer'], int) for p in lists))
        self.assertIn(11217, [p['issuer'] for p in lists])
        self.assertTrue(all(set(p) == {'issuer', 'fromDate', 'toDate'} for p in lists))

    def test_seed_is_identity_only_never_latest(self):
        data = self.run_update(strict=True)
        for c, rows in data['notices'].items():
            if rows:
                self.assertNotEqual(rows[0]['id'], str(mod.ISSUERS[c][0]))
                self.assertEqual(rows[0]['identity_url'], mod.BASE + '/message/' + str(mod.ISSUERS[c][0]))

    def test_sampo_if_remains_hidden_without_verified_identity(self):
        data = self.run_update()
        self.assertEqual(data['notices']['Sampo'], [])
        self.assertEqual(data['coverage']['Sampo']['status'], 'unverified_issuer')

    def test_idempotent_poll_preserves_bytes_mtime_and_timestamp(self):
        self.run_update(strict=True)
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        self.run_update(now=NOW + dt.timedelta(minutes=30), strict=True)
        self.assertEqual((self.path.read_bytes(), self.path.stat().st_mtime_ns), before)

    def test_newer_message_replaces_previous(self):
        before = self.run_update()['notices']['Gjensidige'][0]['id']
        latest = self.row(messageId=999999, publishedTime='2026-11-05T11:00:00Z', title='Newer test notice')
        self.provider.details[999999] = latest
        self.provider.rows[11217].insert(0, latest)
        after = self.run_update()['notices']['Gjensidige']
        self.assertEqual(len(after), 1)
        self.assertNotEqual(before, after[0]['id'])
        self.assertEqual(after[0]['id'], '999999')

    def test_older_response_never_replaces_newer_saved_message(self):
        self.run_update()
        original = self.provider.rows[11217][0].copy()
        new = self.row(messageId=999999, publishedTime='2026-11-05T11:00:00Z')
        self.provider.details[999999] = new
        self.provider.rows[11217] = [new]
        self.run_update()
        self.provider.rows[11217] = [original]
        self.assertEqual(self.run_update()['notices']['Gjensidige'][0]['id'], '999999')

    def test_unsorted_duplicate_rows_choose_one_newest(self):
        rows = self.provider.rows[11217]
        rows.extend([rows[0].copy(), self.row(messageId=111111, publishedTime='2026-09-01T12:00:00Z')])
        data = self.run_update(strict=True)
        self.assertEqual(data['notices']['Gjensidige'][0]['id'], '900001')
        self.assertEqual(len(data['notices']['Gjensidige']), 1)

    def test_expiry_exact_boundary(self):
        at_limit = (NOW - mod.AGE).isoformat()
        self.assertIsNotNone(mod.notice(self.row(publishedTime=at_limit), self.identity, NOW))
        self.assertIsNone(mod.notice(self.row(publishedTime=at_limit), self.identity, NOW + dt.timedelta(seconds=1)))

    def test_future_message_is_not_published(self):
        self.assertIsNone(mod.notice(self.row(publishedTime='2026-11-06T10:00:00Z'), self.identity, NOW))

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(mod.SourceError):
            mod.notice(self.row(publishedTime='2026-11-04T10:00:00'), self.identity, NOW)

    def test_explicit_timezone_normalized(self):
        n = mod.notice(self.row(publishedTime='2026-11-04T11:00:00+01:00'), self.identity, NOW)
        self.assertEqual(n['published_at'], '2026-11-04T10:00:00+00:00')

    def test_wrong_issuer_id_rejected(self):
        with self.assertRaises(mod.SourceError):
            mod.notice(self.row(issuerId=888), self.identity, NOW)

    def test_wrong_issuer_sign_rejected(self):
        with self.assertRaises(mod.SourceError):
            mod.notice(self.row(issuerSign='OTHER'), self.identity, NOW)

    def test_headline_mention_does_not_override_wrong_issuer(self):
        self.provider.rows[11217] = [self.row(issuerId=888, title='Gjensidige results')]
        data = self.run_update()
        self.assertEqual(data['notices']['Gjensidige'], [])
        self.assertIn('Gjensidige', data['errors'])

    def test_test_deleted_cancelled_messages_excluded(self):
        for key in ('test', 'deleted', 'cancelled', 'isDeleted', 'isCancelled'):
            with self.subTest(key=key):
                self.assertIsNone(mod.notice(self.row(**{key: True}), self.identity, NOW))

    def test_blank_title_rejected(self):
        with self.assertRaises(mod.SourceError):
            mod.notice(self.row(title='   '), self.identity, NOW)

    def test_html_application_shell_is_an_error_not_empty_news(self):
        with self.assertRaises(mod.SourceError):
            mod.json_data('<html><div id="root"></div></html>')

    def test_error_envelope_rejected(self):
        with self.assertRaises(mod.SourceError):
            mod.json_data({'error': 'unavailable', 'data': {}})

    def test_missing_list_schema_fails_closed(self):
        client = mod.Client(lambda e, p: {'data': {}})
        with self.assertRaises(mod.SourceError):
            client.listing(self.identity, NOW.date(), NOW.date())

    def test_overflow_bisects_inclusive_dates(self):
        calls = []
        def fetch(e, p):
            calls.append(p)
            return {'data': {'messages': [], 'overflow': p['fromDate'] != p['toDate']}}
        client = mod.Client(fetch)
        client.listing(self.identity, dt.date(2026, 11, 4), dt.date(2026, 11, 5))
        self.assertEqual([(p['fromDate'], p['toDate']) for p in calls],
                         [('2026-11-04','2026-11-05'), ('2026-11-04','2026-11-04'), ('2026-11-05','2026-11-05')])

    def test_single_day_overflow_rejected(self):
        client = mod.Client(lambda e, p: {'data': {'messages': [], 'overflow': True}})
        with self.assertRaises(mod.SourceError):
            client.listing(self.identity, NOW.date(), NOW.date())

    def test_message_detail_mismatch_rejected(self):
        self.provider.details[900001]['title'] = 'different title'
        # Avoid mutating list through Provider's shared dict.
        self.provider.rows[11217] = [self.row(title='original title')]
        data = self.run_update()
        self.assertIn('Gjensidige', data['errors'])

    def test_network_failure_preserves_valid_notice(self):
        old = self.run_update()['notices']
        self.provider.fail = True
        data = self.run_update()
        self.assertEqual(data['notices'], old)
        self.assertEqual(len(data['errors']), 6)

    def test_expiry_applies_even_during_outage(self):
        self.run_update()
        self.provider.fail = True
        data = self.run_update(now=NOW + dt.timedelta(days=93))
        self.assertTrue(all(not rows for rows in data['notices'].values()))

    def test_strict_probe_cannot_pass_on_saved_notices(self):
        self.run_update()
        before = self.path.read_bytes()
        self.provider.fail = True
        with self.assertRaises(mod.SourceError):
            self.run_update(strict=True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_strict_probe_cannot_pass_on_no_recent_messages(self):
        self.provider.rows = {k: [] for k in self.provider.rows}
        with self.assertRaises(mod.SourceError):
            self.run_update(strict=True)
        self.assertFalse(self.path.exists())

    def test_successful_empty_response_is_not_source_error(self):
        self.provider.rows = {k: [] for k in self.provider.rows}
        data = self.run_update()
        self.assertEqual(data['errors'], {})
        self.assertEqual(data['coverage']['Gjensidige']['status'], 'no_recent_notice')

    def test_previous_external_or_spoofed_url_is_not_kept(self):
        n = self.run_update()['notices']['Gjensidige'][0]
        for url in ('javascript:alert(1)', 'https://newsweb.oslobors.no.evil.test/message/1',
                    'https://newsweb.oslobors.no/search', 'http://newsweb.oslobors.no/message/900001'):
            self.assertEqual(mod.previous([{**n, 'url': url}], 'Gjensidige', NOW), [])

    def test_boolean_and_negative_ids_rejected(self):
        for value in (True, False, 0, -1, '1/2', None):
            with self.subTest(value=value), self.assertRaises(mod.SourceError):
                mod.integer(value)

    def test_idempotent_atomic_write_has_no_temp_files(self):
        self.run_update()
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ['newsweb_notices.json'])

    def test_redirect_cannot_leave_official_json_host(self):
        for url in ('https://evil.test/api', 'http://api3.oslo.oslobors.no/api',
                    'https://api3.oslo.oslobors.no:9999/api'):
            with self.assertRaises(mod.SourceError):
                mod.SafeRedirect().redirect_request(None, None, 302, '', {}, url)

    def test_request_cache_avoids_duplicate_detail_fetch(self):
        self.client.message(685479)
        self.client.message(685479)
        calls = [1 for e, p in self.provider.calls if e == 'message' and p['messageId'] == 685479]
        self.assertEqual(len(calls), 1)

    def test_malformed_cached_row_cannot_break_outage_handling(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({'notices': {'Gjensidige': [None, {}, {'published_at': 'bad'}]}}))
        self.provider.fail = True
        self.assertEqual(self.run_update()['notices']['Gjensidige'], [])

    def test_gjensidige_bootstrap_requires_known_numeric_identity(self):
        self.provider.details[685479]['issuerId'] = 999
        with self.assertRaises(mod.SourceError):
            mod.Client(self.provider).identity('Gjensidige')

    def test_seed_issuer_name_change_is_rejected(self):
        self.provider.details[685479]['issuerName'] = 'Another company'
        with self.assertRaises(mod.SourceError):
            mod.Client(self.provider).identity('Gjensidige')


if __name__ == '__main__':
    unittest.main()
