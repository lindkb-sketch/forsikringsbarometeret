#!/usr/bin/env python3
"""Publish verified Storebrand Q3 2026 observations only, fail closed.

Uses official discovery and direct PDF download. Future quarters require an
explicitly reviewed parser; never label Q3 values as a later period.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import date
from storebrand_automation_check import choose_reports, download_pdf
from storebrand_sources import discover
from import_storebrand_reports import parse_group, parse_norway, integrate
from audit_financials import ROOT, audit
from build_verified_feed import build

DATA = ROOT / 'data/financial_observations.json'
FEED = ROOT / 'data/verified_financial_feed.json'


def prepare(group_path, norway_path, group_url, norway_url, baseline,year=2026,quarter=3):
    incoming = parse_group(group_path, group_url,year,quarter) + parse_norway(norway_path, norway_url,year,quarter)
    if len(incoming) != (57 if quarter==3 else 12):
        raise ValueError(f'Unexpected observation count: {len(incoming)}')
    for r in incoming:
        if r['company'] != 'Storebrand' or r['quarter'] not in range(1, 5) or r['year'] not in (year-1, year):
            raise ValueError('Unexpected entity/period in Storebrand importer')
    merged, added, updated = integrate(baseline, incoming)
    feed = build(merged)
    return merged, feed, added, updated


def atomic_json(path, obj):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix='.storebrand-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', type=Path, help='Offline validation PDF')
    parser.add_argument('--norway', type=Path, help='Offline validation PDF')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--year',type=int,default=2026)
    parser.add_argument('--quarter',type=int,default=3)
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--feed', type=Path, default=FEED)
    args = parser.parse_args(argv)
    if (args.group is None) != (args.norway is None):
        parser.error('Supply both offline PDFs or neither')
    if args.quarter not in range(1,5) or args.year < 2025 or (args.year,args.quarter)>(date.today().year,(date.today().month-1)//3+1):
        raise ValueError('Invalid or future Storebrand reporting period')
    baseline = json.loads(args.data.read_text(encoding='utf-8'))
    # Do not allow a Storebrand import to bypass a pre-existing broken dataset.
    before = audit(baseline)
    if not before['ok']:
        raise ValueError('Existing financial data failed audit: ' + str(before['errors']))
    with tempfile.TemporaryDirectory(prefix='storebrand-publish-') as d:
        work = Path(d)
        if args.group:
            group, norway = args.group, args.norway
            group_url = f'https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa/{args.year}'
            norway_url = 'https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-forsikring-as'
        else:
            selected = choose_reports(discover(year=args.year)['reports'], args.year, args.quarter)
            group_url = selected['group']['document_url']
            norway_url = selected['norway']['document_url']
            group, norway = work/'group.pdf', work/'norway.pdf'
            download_pdf(group_url, group)
            download_pdf(norway_url, norway)
        if args.quarter == 4 or (args.year > 2026 and args.quarter in (1,2,3)):
            # Future layouts are parsed only through strict issuer/table checks.
            # Any unrecognized layout raises before financial data is written.
            print('STOREBRAND_NEW_LAYOUT_CHECK',args.year,args.quarter,flush=True)
        merged, feed, added, updated = prepare(group, norway, group_url, norway_url, baseline,args.year,args.quarter)
        # Re-running must not introduce new observations or duplicates.
        repeated, second_added, _ = integrate(merged, parse_group(group, group_url,args.year,args.quarter) + parse_norway(norway, norway_url,args.year,args.quarter))
        if second_added or repeated != merged:
            raise ValueError('Non-idempotent Storebrand import')
        report = {'status': 'passed', 'quarter': f'Q{args.quarter} {args.year}', 'parsed': (57 if args.quarter==3 else 12),
                  'added': added, 'updated_provenance': updated,
                  'dry_run': args.dry_run, 'group_url': group_url, 'norway_url': norway_url}
        if not args.dry_run and (added or updated):
            # Keep other companies' data unchanged; no write until every check passed.
            old_other = [r for r in baseline['observations'] if r['company'] != 'Storebrand']
            new_other = [r for r in merged['observations'] if r['company'] != 'Storebrand']
            if old_other != new_other:
                raise ValueError('Non-Storebrand observations were modified')
            atomic_json(args.data, merged)
            atomic_json(args.feed, feed)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return report

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('STOREBRAND PUBLISH BLOCKED: ' + str(e), file=sys.stderr)
        sys.exit(1)
