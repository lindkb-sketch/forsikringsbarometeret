#!/usr/bin/env python3
"""Publish Gjensidige group quarterly observations only after strict official PDF checks.

No press releases, presentations, estimated values or group-to-Norway substitution.
The newest quarter is optional until the issuer actually releases its PDF.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from audit_financials import DATA, ROOT, audit
from build_verified_feed import OUT, build
from gjensidige_report_check import ARCHIVE, HOME, candidates, fetch
from ingest_official_pdf import download, parse_highlights, read_pdf, merge
import hashlib

REQUIRED = {'insurance_revenue', 'insurance_service_result', 'combined_ratio', 'expense_ratio'}
KEYS = ('company', 'year', 'quarter', 'scope', 'period_type', 'metric')

def discover_quarter(quarter, year=2026, fetcher=fetch):
    urls = set()
    failures = []
    for index in (ARCHIVE, HOME):
        try:
            urls.update(candidates(fetcher(index), index, quarter, year))
        except Exception as exc:
            failures.append(f'{index}: {exc}')
    if len(failures) == 2:
        raise ValueError('All official Gjensidige indexes failed: ' + '; '.join(failures))
    if len(urls) > 1:
        raise ValueError(f'Ambiguous Gjensidige Q{quarter} PDF candidates: {sorted(urls)}')
    return next(iter(urls)) if urls else None

def prepare(existing, quarters, year=2026, fetcher=fetch, downloader=download):
    if not audit(existing)['ok']:
        raise ValueError('Baseline financial observations failed audit')
    staged = []
    source_urls = {}
    for quarter in quarters:
        url = discover_quarter(quarter, year, fetcher)
        if url is None:
            if quarter in (1, 2):
                raise ValueError(f'Official Gjensidige Q{quarter} {year} report PDF not found')
            continue
        blob = downloader(url)
        if not blob.startswith(b'%PDF-'):
            raise ValueError('Downloaded document is not a PDF')
        pages = read_pdf(blob)
        opening = ' '.join(text for _, text in pages[:2]).lower()
        name = ['first', 'second', 'third', 'fourth'][quarter-1]
        if ('gjensidige' not in opening or str(year) not in opening or
            not (f'{name} quarter' in opening or re.search(rf'\b{quarter}(?:st|nd|rd|th) quarter\b', opening))):
            raise ValueError(f'PDF cover does not identify Gjensidige Q{quarter} {year}')
        sha = hashlib.sha256(blob).hexdigest()
        rows = parse_highlights(pages, 'Gjensidige', year, quarter, url, sha)
        found = {r['metric'] for r in rows if r['period_type'] == 'quarter'}
        if not REQUIRED <= found:
            raise ValueError(f'Gjensidige Q{quarter} {year} missing verified quarterly metrics: {sorted(REQUIRED-found)}')
        if any(r['company'] != 'Gjensidige' or r['scope'] != 'group' or
               r['quarter'] != quarter or r['year'] != year for r in rows):
            raise ValueError('Cross-period or scope contamination')
        staged.extend(rows)
        source_urls[f'Q{quarter}'] = url
    merged, added = merge(existing, staged)
    feed = build(merged)
    repeated, again = merge(merged, staged)
    if again or repeated != merged:
        raise ValueError('Gjensidige import is not idempotent')
    old_other = [r for r in existing['observations'] if r['company'] != 'Gjensidige']
    new_other = [r for r in merged['observations'] if r['company'] != 'Gjensidige']
    if old_other != new_other:
        raise ValueError('Non-Gjensidige records changed')
    return merged, feed, {'added': added, 'parsed': len(staged), 'reports': source_urls}

def write_json(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.gjensidige-', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--data', type=Path, default=DATA)
    p.add_argument('--feed', type=Path, default=OUT)
    args = p.parse_args()
    existing = json.loads(args.data.read_text(encoding='utf-8'))
    merged, feed, summary = prepare(existing, (1, 2, 3))
    if not args.dry_run and summary['added']:
        write_json(args.data, merged)
        write_json(args.feed, feed)
    print(json.dumps({'status':'validated', 'dry_run':args.dry_run, **summary}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('GJENSIDIGE PUBLISH BLOCKED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
