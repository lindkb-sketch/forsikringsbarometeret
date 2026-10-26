#!/usr/bin/env python3
"""Auditable four-quarter profitability coverage for every insurer.

No estimate or archived JavaScript value is allowed to fill source-data gaps.
This report is regenerated before every GitHub Pages publication.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANIES = ('Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende', 'Protector', 'Storebrand')
METRICS = ('combined_ratio', 'loss_ratio', 'expense_ratio')

def window(year, quarter):
    index = year * 4 + quarter - 1
    return [(int((index - i) // 4), int((index - i) % 4) + 1) for i in (3, 2, 1, 0)]

def audit(observations, year=None, quarter=None):
    valid = [r for r in observations if r.get('scope') == 'group' and
             r.get('period_type') == 'quarter' and
             r.get('status') in ('reported', 'calculated') and
             r.get('metric') in METRICS and
             isinstance(r.get('value'), (float, int)) and
             r.get('source_url', '').startswith('https://')]
    if year is None or quarter is None:
        dates = sorted((r['year'], r['quarter']) for r in valid)
        if not dates:
            raise ValueError('No verified quarterly profitability observations')
        year, quarter = dates[-1]
    quarters = window(year, quarter)
    keys = {(r['company'], r['year'], r['quarter'], r['metric']) for r in valid}
    companies = []
    for company in COMPANIES:
        slots = []
        for y, q in quarters:
            missing = [metric for metric in METRICS if (company, y, q, metric) not in keys]
            slots.append({
                'period': f'Q{q} {y}',
                'verified': not missing,
                'missing_metrics': missing,
                'status': 'verified' if not missing else 'missing_verified_source'
            })
        companies.append({
            'company': company, 'quarters': slots,
            'complete': all(slot['verified'] for slot in slots),
        })
    return {
        'reference_period': f'Q{quarter} {year}',
        'window': [f'Q{q} {y}' for y, q in quarters],
        'companies': companies,
        'fully_covered': all(company['complete'] for company in companies),
        'rule': 'No numeric fallback, synthetic value, or hardcoded chart history'
    }

def main():
    feed = json.loads((ROOT / 'data/verified_financial_feed.json').read_text(encoding='utf-8'))
    report = audit(feed['observations'])
    target = ROOT / 'data/profitability_coverage.json'
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for company in report['companies']:
        missing = [p['period'] for p in company['quarters'] if not p['verified']]
        print('PROFITABILITY_COVERAGE', company['company'], 'verified' if not missing else 'MISSING',
              ', '.join(missing) or '-', flush=True)
    print('PROFITABILITY_COMPLETE', report['fully_covered'], 'report:', target)

if __name__ == '__main__':
    main()
