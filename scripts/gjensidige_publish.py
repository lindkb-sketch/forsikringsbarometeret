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
from datetime import date
from pathlib import Path

from audit_financials import DATA, ROOT, audit
from build_verified_feed import OUT, build
from gjensidige_report_check import ARCHIVE, HOME, candidates, official_report_links, fetch
from ingest_official_pdf import download, parse_highlights, read_pdf, merge
import hashlib

REQUIRED = {'insurance_revenue', 'insurance_service_result', 'combined_ratio', 'expense_ratio'}
KEYS = ('company', 'year', 'quarter', 'scope', 'period_type', 'metric')

# Reference figures checked against official Q1/Q2 2026 Group highlights tables.
# A mismatch must stop publication, not silently change financial history.
REFERENCE_QUARTER = {
    (2026, 1): {'insurance_revenue': 11004.1, 'insurance_service_result': 2288.1,
                'combined_ratio': 79.2, 'expense_ratio': 11.7, 'loss_ratio': 67.5},
    (2026, 2): {'insurance_revenue': 11257.8, 'insurance_service_result': 2375.0,
                'combined_ratio': 78.9, 'expense_ratio': 11.7, 'loss_ratio': 67.2},
}

# Official PDF URLs independently verified from Gjensidige's investor-relations page.
APPROVED_PDFS = {
    (2026, 1): 'https://mb.cision.com/Public/1122/4341796/af7aaae92042a970.pdf',
    (2026, 2): 'https://mb.cision.com/Public/1122/4373892/b3fb98691b4814f0.pdf',
}


def discover_quarter(quarter, year=2026, fetcher=fetch):
    if (year, quarter) in APPROVED_PDFS:
        return APPROVED_PDFS[(year, quarter)]
    urls = set()
    failures = []
    for index in (ARCHIVE, HOME):
        try:
            page = fetcher(index)
            urls.update(candidates(page, index, quarter, year))
            if index == HOME:
                urls.update(official_report_links(page, index, quarter, year))
        except Exception as exc:
            failures.append(f'{index}: {exc}')
    if len(failures) == 2:
        raise ValueError('All official Gjensidige indexes failed: ' + '; '.join(failures))
    if len(urls) > 1:
        raise ValueError(f'Ambiguous Gjensidige Q{quarter} PDF candidates: {sorted(urls)}')
    return next(iter(urls)) if urls else None

def parse_group_table(pages, year, quarter, url, sha):
    """Read Group highlights' numerical table, not the two-column narrative.

    On the official Gjensidige PDFs the group table is on printed page 3
    (PDF page 4), with current-quarter values in the first numeric column
    and YTD in the third for Q2 onward.
    """
    labels = {
        'insurance_revenue': 'Insurance revenue from general insurance',
        'insurance_service_result': 'Insurance service result general insurance',
        'combined_ratio': 'Combined ratio',
        'expense_ratio': 'Cost ratio',
        'loss_ratio': 'Loss ratio, net of reinsurance',
    }
    table_pages = [(p, text) for p, text in pages if
                   'Insurance service result general insurance' in text and
                   'Insurance revenue from general insurance' in text and
                   'NOK millions' in text]
    if len(table_pages) != 1:
        raise ValueError('Cannot uniquely locate Gjensidige group highlights table')
    page, text = table_pages[0]
    lines = text.splitlines()
    result = []
    for metric, label in labels.items():
        matching = [line for line in lines if
                    re.match(r'^\s*' + re.escape(label) + r'(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+)?\s+', line, re.I)]
        if len(matching) != 1:
            if metric == 'loss_ratio':
                continue
            raise ValueError(f'Ambiguous Gjensidige group table metric: {metric}')
        remainder = matching[0][len(label):]
        remainder = re.sub(r'^[¹²³⁴⁵⁶⁷⁸⁹⁰\s]+', '', remainder)
        values = re.findall(r'(?<![A-Za-z0-9])[-]?\d[\d,]*\.\d+(?!\d)', remainder)
        if len(values) < (3 if quarter > 1 else 1):
            raise ValueError(f'Insufficient group table columns for {metric}')
        columns=(
            [('quarter',year,0),('quarter',year-1,1)]
            if quarter==1 else
            [('quarter',year,0),('quarter',year-1,1),
             ('ytd',year,2),('ytd',year-1,3)]
        )
        if len(values)<(2 if quarter==1 else 4):
            raise ValueError('Gjensidige prior-year comparative columns missing')
        for period,observation_year,index in columns:
            result.append(dict(company='Gjensidige', year=observation_year, quarter=quarter,
                scope='group', source_scope='group', period_type=period, metric=metric,
                value=float(values[index].replace(',', '')),
                unit='percent' if 'ratio' in metric else 'MNOK', status='reported',
                source_url=url, source_type='official_quarterly_report',
                source_page=page, source_sha256=sha,
                source_document_period=f'Q{quarter} {year}',
                source_section='Group highlights / Alternative performance measures'+
                 (' / prior-year comparative column' if observation_year!=year else '')))
    return result

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
        rows = parse_group_table(pages, year, quarter, url, sha)
        reference = REFERENCE_QUARTER.get((year, quarter))
        if reference:
            actual = {r['metric']: r['value'] for r in rows if r['period_type'] == 'quarter'}
            for metric, expected in reference.items():
                if metric not in actual or abs(actual[metric] - expected) > 0.051:
                    raise ValueError(f'Official Gjensidige Q{quarter} reference mismatch: {metric}')
        found = {r['metric'] for r in rows if r['period_type'] == 'quarter'}
        if not REQUIRED <= found:
            raise ValueError(f'Gjensidige Q{quarter} {year} missing verified quarterly metrics: {sorted(REQUIRED-found)}')
        if any(r['company'] != 'Gjensidige' or r['scope'] != 'group' or
               r['quarter'] != quarter or r['year'] not in (year,year-1) for r in rows):
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
    today = date.today()
    # Inspect every elapsed quarter from 2026 onward. The current quarter is
    # included so newly released reports are picked up on the next scheduled run.
    periods = [(year, quarter) for year in range(2026, today.year + 1)
               for quarter in range(1, 5)
               if (year, quarter) <= (today.year, (today.month - 1) // 3 + 1)]
    merged, feed, summary = existing, build(existing), {'added': 0, 'parsed': 0, 'reports': {}}
    for year in sorted({year for year, _ in periods}):
        quarters = [quarter for y, quarter in periods if y == year]
        merged, feed, batch = prepare(merged, quarters, year=year)
        summary['added'] += batch['added']
        summary['parsed'] += batch['parsed']
        summary['reports'].update({f'{year}-{key}': url for key, url in batch['reports'].items()})
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
