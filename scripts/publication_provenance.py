#!/usr/bin/env python3
"""Auditable per-issuer source -> validated feed -> public Pages parity manifest.

This proves provenance and byte-for-byte observation parity for the latest
already-verified quarter, NOT automatic discovery of a newly released report.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
COMPANIES = ('Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende', 'Protector', 'Storebrand')
KEYS = ('company', 'year', 'quarter', 'scope', 'period_type', 'metric', 'segment')

def observation_key(row):
    return tuple(row.get(key, '') for key in KEYS)

def digest(rows):
    payload = json.dumps(sorted(rows, key=lambda r: repr(observation_key(r))),
                         ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def build(source, feed):
    if not isinstance(source, list) or not isinstance(feed, list):
        raise ValueError('Source and feed observations must be lists')
    source_index = {}
    feed_index = {}
    for rows, index, label in ((source, source_index, 'source'), (feed, feed_index, 'feed')):
        for row in rows:
            if row.get('company') not in COMPANIES:
                continue
            key = observation_key(row)
            if key in index:
                raise ValueError(f'Duplicate {label} observation: {key}')
            index[key] = row
    results = []
    for company in COMPANIES:
        current = [row for row in source if row.get('company') == company
                   and row.get('scope') == 'group'
                   and row.get('period_type') == 'quarter'
                   and row.get('status', 'reported') in ('reported', 'calculated')]
        if not current:
            raise ValueError(f'{company}: no verified group-quarter observations')
        year, quarter = max((row['year'], row['quarter']) for row in current)
        selected = [row for row in current if (row['year'], row['quarter']) == (year, quarter)]
        for row in selected:
            url = row.get('source_url', '')
            parsed = urlparse(url)
            if parsed.scheme != 'https' or not parsed.netloc:
                raise ValueError(f'{company}: missing HTTPS source: {observation_key(row)}')
            if row.get('source_type') != 'official_quarterly_report':
                raise ValueError(f'{company}: non-official source: {observation_key(row)}')
            key = observation_key(row)
            if feed_index.get(key) != row:
                raise ValueError(f'{company}: missing or altered published observation: {key}')
        keys = {observation_key(row) for row in selected}
        feed_selected = [row for row in feed if observation_key(row) in keys]
        if len(feed_selected) != len(selected):
            raise ValueError(f'{company}: publication row count differs')
        results.append({
            'company': company, 'latest_verified_period': f'{year}-Q{quarter}',
            'group_quarter_observations': len(selected),
            'official_source_urls': sorted({row['source_url'] for row in selected}),
            'observation_sha256': digest(selected),
            'source_to_feed_parity': True,
            'public_pages_parity': 'pending_deployment_check',
            'new_report_discovery_proven': False,
            'fully_automatic_certified': False,
        })
    return {'schema_version': 1, 'status': 'SOURCE_TO_FEED_VERIFIED_PUBLIC_PENDING',
            'limitation': 'Existing source metadata and feed parity do not prove autonomous discovery or fresh source download.',
            'companies': results}

def main():
    root = ROOT / 'data'
    source = json.loads((root / 'financial_observations.json').read_text(encoding='utf-8'))['observations']
    feed = json.loads((root / 'verified_financial_feed.json').read_text(encoding='utf-8'))['observations']
    result = build(source, feed)
    target = root / 'publication_provenance.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for company in result['companies']:
        print('SOURCE_TO_FEED_PROVEN', company['company'], company['latest_verified_period'],
              company['group_quarter_observations'], company['observation_sha256'])
    print('Manifest:', target)

if __name__ == '__main__':
    main()
