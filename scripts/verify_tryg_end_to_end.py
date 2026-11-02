#!/usr/bin/env python3
"""Report Tryg PDF-only group/Norway coverage without spreadsheet dependencies."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def assess(sources,workbooks,observations):
    # Retain the historical call signature for existing callers; never use workbooks.
    pdfs=[s for s in sources if s.get('company')=='Tryg'
          and str(s.get('document_url','')).startswith('https://')
          and str(s.get('document_url','')).lower().split('?')[0].endswith('.pdf')
          and s.get('year') and s.get('quarter')]
    def periods(scope):
        return sorted({(r['year'],r['quarter']) for r in observations
            if r.get('company')=='Tryg' and r.get('scope')==scope
            and r.get('period_type')=='quarter'
            and str(r.get('source_url','')).startswith('https://')
            and r.get('source_type') in ('official_quarterly_report','official_annual_report')})
    return {'registered_group_pdf_quarters':sorted({(s['year'],s['quarter']) for s in pdfs}),
            'observed_group_quarters':periods('group'),
            'observed_norway_quarters':periods('norway'),
            'group_pdf_automatic':bool(periods('group')),
            'norway_pdf_automatic':bool(periods('norway')),
            'reason':'PDF source-linked observations only; completeness must be checked separately'}

def run():
    sources=json.loads((ROOT/'data/report_sources.json').read_text())['sources']
    rows=json.loads((ROOT/'data/financial_observations.json').read_text())['observations']
    print(json.dumps(assess(sources,[],rows),ensure_ascii=False))
if __name__=='__main__':run()
