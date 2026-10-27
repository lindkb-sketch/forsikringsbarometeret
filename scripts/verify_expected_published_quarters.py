#!/usr/bin/env python3
"""Block green deployment when published issuer quarters lack expected site coverage.

This gate checks source-to-site completeness, not just source/feed parity.
Never substitutes group or Nordic figures for Norwegian segments.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
METRICS={'insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio'}
COMPANIES={'Gjensidige','Tryg','Protector','Storebrand','Fremtind','Sampo','Frende'}

def validate(rows):
    errors=[]
    def metrics(company,year,quarter,scope,segment=None):
        return {r['metric'] for r in rows if r.get('company')==company
            and r.get('year')==year and r.get('quarter')==quarter
            and r.get('period_type')=='quarter' and r.get('scope')==scope
            and (scope!='reported_segment' or r.get('segment')==segment)
            and r.get('status') in ('reported','calculated')}
    for company in sorted(COMPANIES):
        periods=sorted({(r['year'],r['quarter']) for r in rows
            if r.get('company')==company and r.get('scope')=='group'
            and r.get('period_type')=='quarter' and r.get('year',0)>=2026})
        for year,quarter in periods:
            found=metrics(company,year,quarter,'group')
            missing=METRICS-found
            if missing:errors.append(f'{company} Q{quarter} {year} group missing {sorted(missing)}')
            # The site must have an official, same-quarter revenue comparator to
            # calculate its growth; a missing prior year is a visible coverage gap.
            if 'insurance_revenue' in found and 'insurance_revenue' not in metrics(company,year-1,quarter,'group'):
                errors.append(f'{company} Q{quarter} {year} revenue growth comparator missing')
            if company=='Tryg':
                for scope in ('group','norway'):
                    current=next((r for r in rows if r.get('company')==company and
                        r.get('year')==year and r.get('quarter')==quarter and
                        r.get('scope')==scope and r.get('period_type')=='quarter' and
                        r.get('metric')=='insurance_revenue'),None)
                    prior=next((r for r in rows if r.get('company')==company and
                        r.get('year')==year-1 and r.get('quarter')==quarter and
                        r.get('scope')==scope and r.get('period_type')=='quarter' and
                        r.get('metric')=='insurance_revenue'),None)
                    if current and prior and (not current.get('unit') or
                        current.get('unit')!=prior.get('unit')):
                        errors.append(f'Tryg Q{quarter} {year} {scope} revenue growth units missing/incompatible')
                    if current and not prior:
                        errors.append(f'Tryg Q{quarter} {year} {scope} revenue growth prior period missing')
            if company=='Gjensidige':
                for scope,segment in [('norway',None),('reported_segment','Private Norway'),
                                      ('reported_segment','Commercial Norway')]:
                    absent=METRICS-metrics(company,year,quarter,scope,segment)
                    if absent:errors.append(f'{company} Q{quarter} {year} {segment or scope} missing {sorted(absent)}')
            elif company in ('Tryg','Protector','Storebrand'):
                # These issuers have independently verified Norway reporting.
                # If it was available for the preceding quarter, its absence
                # in a newly reported group quarter requires investigation.
                if metrics(company,year,quarter-1,'norway') and not metrics(company,year,quarter,'norway'):
                    errors.append(f'{company} Q{quarter} {year} Norway import absent')
    if errors:raise ValueError('Published-quarter coverage failed:\\n'+'\\n'.join(errors))
    return True

if __name__=='__main__':
    rows=json.loads((ROOT/'data/verified_financial_feed.json').read_text(encoding='utf-8'))['observations']
    validate(rows)
    print('Published-quarter company, Norway and growth coverage verified')
