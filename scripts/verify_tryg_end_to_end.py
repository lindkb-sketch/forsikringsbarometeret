#!/usr/bin/env python3
"""Report Tryg's actual PDF-based group and Norway import coverage."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def assess(sources, observations):
    group = [s for s in sources if s.get('company') == 'Tryg'
             and str(s.get('document_url', '')).lower().split('?')[0].endswith('.pdf')
             and s.get('year') and s.get('quarter')]
    group_periods = sorted({(s['year'], s['quarter']) for s in group})
    observed_group = sorted({(r['year'], r['quarter']) for r in observations
                            if r.get('company') == 'Tryg' and r.get('scope') == 'group'
                            and r.get('period_type') == 'quarter'})
    observed_norway = sorted({(r['year'], r['quarter']) for r in observations
                             if r.get('company') == 'Tryg' and r.get('scope') == 'norway'
                             and r.get('period_type') == 'quarter'
                             and r.get('source_type') == 'official_quarterly_report'})
    return {
        'registered_group_pdf_quarters': group_periods,
        'observed_group_quarters': observed_group,
        'observed_norway_pdf_quarters': observed_norway,
        'pdf_only': True,
        'group_pdf_automatic': bool(group_periods and observed_group),
        'norway_pdf_automatic': bool(observed_norway),
        'note': 'No spreadsheet candidate registry or workbook used for this diagnostic.'
    }

def run():
    sources = json.loads((ROOT / 'data/report_sources.json').read_text())['sources']
    rows = json.loads((ROOT / 'data/financial_observations.json').read_text())['observations']
    print(json.dumps(assess(sources, rows), ensure_ascii=False))

if __name__ == '__main__':
    run()
