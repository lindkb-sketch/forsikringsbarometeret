#!/usr/bin/env python3
"""Honest Tryg PDF-group/XLSX-Norway automation readiness gate."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def assess(sources,workbooks,observations):
    group=[s for s in sources if s.get('company')=='Tryg' and s.get('document_url') and s.get('year') and s.get('quarter')]
    norway=[w for w in workbooks if w.get('company')=='Tryg' and w.get('approved')]
    periods={('group',r['year'],r['quarter']) for r in observations if r.get('company')=='Tryg' and r.get('scope')=='group' and r.get('period_type')=='quarter'}
    periods|={('norway',r['year'],r['quarter']) for r in observations if r.get('company')=='Tryg' and r.get('scope')=='norway' and r.get('period_type')=='quarter'}
    return {'registered_group_pdf_quarters':sorted({(s['year'],s['quarter']) for s in group}),
            'registered_norway_xlsx_quarters':sorted({(w['year'],w['quarter']) for w in norway}),
            'observed_group_quarters':sorted((y,q) for scope,y,q in periods if scope=='group'),
            'observed_norway_quarters':sorted((y,q) for scope,y,q in periods if scope=='norway'),
            'group_pdf_automatic':False,
            'norway_xlsx_automatic':False,
            'reason':'Tryg official quarterly PDF group parser and dynamically discovered Norway XLSX have not been end-to-end verified'}

def run():
    sources=json.loads((ROOT/'data/report_sources.json').read_text())['sources']
    workbooks=json.loads((ROOT/'data/geographic_workbooks.json').read_text())['workbooks']
    rows=json.loads((ROOT/'data/financial_observations.json').read_text())['observations']
    print(json.dumps(assess(sources,workbooks,rows),ensure_ascii=False))
if __name__=='__main__':run()
