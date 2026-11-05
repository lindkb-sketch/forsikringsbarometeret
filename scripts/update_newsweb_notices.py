#!/usr/bin/env python3
"""Import NewsWeb metadata, never the JavaScript application shell.

Only title, publication time, issuer identity and the canonical NewsWeb link
are published. Seed messages establish issuer identity; they are NOT used as
"latest" messages. Every poll queries the issuer's current 92-day window.
The public website's JSON endpoint is not a versioned service guarantee:
unknown schemas and incomplete responses must fail closed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/newsweb_notices.json'
BASE = 'https://newsweb.oslobors.no'
API = 'https://api3.oslo.oslobors.no/v1/newsreader'
COMPANIES = ('Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende', 'Protector', 'Storebrand')
AGE = dt.timedelta(days=92)
UTC = dt.timezone.utc
# Identity evidence: the named issuer on each public /message/<id> page.
# Resolve numeric issuerId + issuerSign from that same message on every run.
# Do not infer identities from words in a headline or use an owner's notices.
ISSUERS = {
    'Fremtind': (683603, 'Fremtind Forsikring AS'),
    'Gjensidige': (685479, 'Gjensidige Forsikring ASA'),
    'Tryg': (684542, 'Tryg Forsikring A/S'),
    'Frende': (684953, 'Frende Skadeforsikring AS'),
    'Protector': (685366, 'Protector Forsikring ASA'),
    'Storebrand': (685311, 'Storebrand ASA'),
}
# No verified NewsWeb issuer identity for If/Sampo yet. Its box remains hidden;
# Bank Norwegian or other issuers merely mentioning Sampo must never be used.


class SourceError(ValueError):
    """Untrusted or incomplete source response."""


def integer(value):
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise SourceError('Expected a positive numeric NewsWeb ID')
    return int(value)


def timestamp(value):
    if not isinstance(value, str):
        raise SourceError('Missing publication timestamp')
    try:
        result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise SourceError('Invalid publication timestamp') from exc
    if result.tzinfo is None:
        raise SourceError('Publication timestamp lacks a timezone')
    return result.astimezone(UTC)


def json_data(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), dict):
        raise SourceError('Expected NewsWeb JSON data object, not HTML')
    if payload.get('error') or payload.get('errors'):
        raise SourceError('NewsWeb returned an error')
    return payload['data']


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme, target.hostname, target.port) != ('https', 'api3.oslo.oslobors.no', None):
            raise SourceError('Unexpected NewsWeb API redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_json(endpoint, params):
    if endpoint not in ('message', 'list'):
        raise SourceError('Unknown NewsWeb endpoint')
    url = API + '/' + endpoint + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Forsikringsbarometeret/1.0 (NewsWeb metadata reader)',
        'Accept': 'application/json',
        'Origin': BASE,
        'Referer': BASE + '/',
    })
    with urllib.request.build_opener(SafeRedirect()).open(request, timeout=25) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname != 'api3.oslo.oslobors.no':
            raise SourceError('Unexpected response host')
        if 'json' not in response.headers.get('Content-Type', '').lower():
            raise SourceError('NewsWeb did not return JSON')
        body = response.read(4_000_001)
    if len(body) > 4_000_000:
        raise SourceError('NewsWeb response exceeds size limit')
    try:
        return json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise SourceError('Invalid NewsWeb JSON') from exc


class Client:
    def __init__(self, fetcher=fetch_json):
        self.fetcher = fetcher
        self.cache = {}
        self.requests = 0

    def get(self, endpoint, params):
        key = (endpoint, tuple(sorted(params.items())))
        if key not in self.cache:
            self.requests += 1
            if self.requests > 60:
                raise SourceError('NewsWeb request budget exceeded')
            self.cache[key] = self.fetcher(endpoint, params)
        return self.cache[key]

    def message(self, message_id):
        mid = integer(message_id)
        message = json_data(self.get('message', {'messageId': mid})).get('message')
        if not isinstance(message, dict) or integer(message.get('messageId')) != mid:
            raise SourceError('Message detail ID mismatch')
        return message

    def identity(self, company):
        seed, name = ISSUERS[company]
        message = self.message(seed)
        issuer_id = integer(message.get('issuerId'))
        sign = message.get('issuerSign')
        if not isinstance(sign, str) or not sign.strip() or len(sign) > 40:
            raise SourceError('Missing issuer code on identity evidence')
        # Some endpoint versions include issuerName, others only issuerSign.
        # The verified seed ID is the identity anchor in both cases.
        actual_name = message.get('issuerName')
        if actual_name is not None and (not isinstance(actual_name, str) or
                actual_name.casefold().strip() != name.casefold()):
            raise SourceError('Issuer name changed on identity evidence')
        if company == 'Gjensidige' and (issuer_id, sign) != (11217, 'GJF'):
            raise SourceError('Gjensidige issuer identity mismatch')
        return {'issuer_id': issuer_id, 'issuer_sign': sign, 'issuer_name': name,
                'identity_url': BASE + '/message/' + str(seed)}

    def listing(self, identity, start, end):
        params = {'issuer': identity['issuer_id'], 'fromDate': start.isoformat(),
                  'toDate': end.isoformat()}
        data = json_data(self.get('list', params))
        rows = data.get('messages')
        if not isinstance(rows, list) or not isinstance(data.get('overflow'), bool):
            raise SourceError('Unexpected NewsWeb list schema')
        if data['overflow']:
            if start >= end:
                raise SourceError('Incomplete NewsWeb result even for one day')
            middle = start + dt.timedelta(days=(end - start).days // 2)
            return (self.listing(identity, start, middle) +
                    self.listing(identity, middle + dt.timedelta(days=1), end))
        for row in rows:
            if not isinstance(row, dict):
                raise SourceError('Invalid NewsWeb message row')
            if (integer(row.get('issuerId')) != identity['issuer_id'] or
                    row.get('issuerSign') != identity['issuer_sign']):
                raise SourceError('NewsWeb issuer filter returned another issuer')
        return rows


def notice(row, identity, now):
    if (integer(row.get('issuerId')) != identity['issuer_id'] or
            row.get('issuerSign') != identity['issuer_sign']):
        raise SourceError('Message belongs to a different issuer')
    mid = integer(row.get('messageId'))
    when = timestamp(row.get('publishedTime'))
    if any(row.get(key) for key in ('test', 'deleted', 'cancelled', 'isDeleted', 'isCancelled')):
        return None
    if not dt.timedelta(0) <= now - when <= AGE:
        return None
    title = row.get('title')
    if not isinstance(title, str) or not title.strip() or len(title) > 2000:
        raise SourceError('Missing or invalid message title')
    title = ' '.join(title.split())
    return {'source': 'NewsWeb', 'id': str(mid), 'title': title,
            'url': BASE + '/message/' + str(mid), 'published_at': when.isoformat(),
            **identity}


def previous(rows, company, now):
    """Keep only validated, still-young notices during a source outage."""
    valid = []
    if not isinstance(rows, list) or company not in ISSUERS:
        return valid
    for row in rows:
        try:
            mid = integer(row.get('id'))
            if (row.get('source') != 'NewsWeb' or
                    row.get('url') != BASE + '/message/' + str(mid) or
                    row.get('issuer_name') != ISSUERS[company][1] or
                    row.get('identity_url') != BASE + '/message/' + str(ISSUERS[company][0]) or
                    not isinstance(row.get('title'), str) or not row['title'].strip()):
                continue
            integer(row.get('issuer_id'))
            if not dt.timedelta(0) <= now - timestamp(row.get('published_at')) <= AGE:
                continue
            valid.append(row)
        except (ValueError, TypeError, AttributeError):
            continue
    return sorted(valid, key=lambda x: (timestamp(x['published_at']), integer(x['id'])), reverse=True)[:1]


def write_changed(path, payload):
    """Write atomically, preserving file bytes and updated_at for unchanged data."""
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    comparable = lambda obj: {k: v for k, v in obj.items() if k != 'updated_at'}
    if isinstance(old, dict) and comparable(old) == comparable(payload):
        return old
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.newsweb-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return payload


def update(fetcher=fetch_json, now=None, out=OUT, strict=False):
    now = now or dt.datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError('Current time must include a timezone')
    now = now.astimezone(UTC)
    out = Path(out)
    old = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    old_notices = old.get('notices', {})
    if not isinstance(old_notices, dict):
        old_notices = {}
    client = Client(fetcher)
    result = {'source': 'NewsWeb', 'updated_at': now.isoformat(),
              'notices': {c: [] for c in COMPANIES}, 'coverage': {}, 'errors': {}}
    for company in COMPANIES:
        if company not in ISSUERS:
            result['coverage'][company] = {'status': 'unverified_issuer',
                'reason': 'No verified NewsWeb issuer for If/Sampo; no substitute source used'}
            continue
        try:
            identity = client.identity(company)
            rows = client.listing(identity, (now - AGE).date(), now.date())
            candidates = [n for row in rows if (n := notice(row, identity, now))]
            newest = max(candidates, key=lambda n: (timestamp(n['published_at']), integer(n['id'])), default=None)
            if newest:
                detail = notice(client.message(newest['id']), identity, now)
                if detail is None or any(detail[k] != newest[k] for k in ('id', 'title', 'published_at')):
                    raise SourceError('Latest list entry and message detail do not agree')
                saved = previous(old_notices.get(company, []), company, now)
                # A temporarily stale list must not move the displayed news backwards.
                if saved and timestamp(saved[0]['published_at']) > timestamp(detail['published_at']):
                    result['notices'][company] = saved
                else:
                    result['notices'][company] = [detail]
            result['coverage'][company] = {**identity,
                'status': 'ok' if newest else 'no_recent_notice'}
        except (SourceError, OSError, ValueError, TypeError, KeyError) as exc:
            result['notices'][company] = previous(old_notices.get(company, []), company, now)
            result['errors'][company] = f'{type(exc).__name__}: {str(exc)[:180]}'
            result['coverage'][company] = {'status': 'source_error'}
    if strict and (result['errors'] or not any(result['notices'].values())):
        raise SourceError('Live ingestion not proven: ' + json.dumps(result['errors'], ensure_ascii=False))
    return write_changed(out, result)


def probe():
    """Exercise the REAL updater, actual JSON write/read, and idempotency."""
    cache = Client()
    now = dt.datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix='newsweb-probe-') as directory:
        path = Path(directory) / 'data/newsweb_notices.json'
        payload = update(cache.get, now=now, out=path, strict=True)
        persisted = json.loads(path.read_text(encoding='utf-8'))
        if persisted != payload:
            raise SourceError('Written feed does not match verified result')
        before = path.read_bytes()
        update(cache.get, now=now, out=path, strict=True)
        if path.read_bytes() != before:
            raise SourceError('Identical source response rewrote the feed')
        proof = {'source': API, 'checked_at': now.isoformat(),
                 'sha256': hashlib.sha256(before).hexdigest(),
                 'written_and_read_back': True, 'idempotent': True,
                 'coverage': payload['coverage'],
                 'latest': {c: rows[0] if rows else None for c, rows in payload['notices'].items()}}
        print('NEWSWEB_PROBE_OK ' + json.dumps(proof, ensure_ascii=False), flush=True)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true', help='Live integration gate; never changes repository data')
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    try:
        if args.probe:
            probe()
        else:
            data = update(out=args.output)
            for company, error in data['errors'].items():
                print(f'::warning::{company}: NewsWeb update failed; retaining validated unexpired notice. {error}')
            print('NEWSWEB_FEED', data['updated_at'], {c: len(v) for c, v in data['notices'].items()})
    except (SourceError, OSError, ValueError) as exc:
        print('NEWSWEB_PROBE_FAILED: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
