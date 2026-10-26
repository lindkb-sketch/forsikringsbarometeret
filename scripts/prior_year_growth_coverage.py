#!/usr/bin/env python3
"""Auditable prior-year growth evidence for every insurer, each quarter and YTD.

Read only published, source-backed observation rows. Never extrapolate from
a different quarter, legal scope or revenue definition.
"""
import json
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

ROOT=Path(__file__).resolve().parents[1]
COMPANIES=('Fremtind','Gjensidige','Tryg','Protector','Storebrand','Sampo','Frende')
def basis(row):
    description=(row.get('source_definition') or '').lower()
    if 'sum driftsinntekter' in description or 'group operating revenue' in description:
        return 'operating_revenue'
    if 'premiums f.o.a.' in description or 'not ifrs insurance revenue' in description:
        return 'insurance_premiums_apm'
    return 'insurance_revenue'

def evidence(observations, current_year=2026, quarter=3):
    out=[]
    for company in COMPANIES:
        details={'company':company}
        for kind in ('quarter','ytd'):
            samples={}
            for year in (current_year-1,current_year-2):
                matches=[r for r in observations if r.get('company')==company
                         and r.get('scope')=='group' and r.get('year')==year
                         and r.get('quarter')==quarter and r.get('period_type')==kind
                         and r.get('metric')=='insurance_revenue'
                         and r.get('status','reported') in ('reported','calculated')
                         and str(r.get('source_url','')).startswith('https://')
                         and r.get('source_type')=='official_quarterly_report']
                if len(matches)==1:samples[year]=matches[0]
            now=samples.get(current_year-1)
            then=samples.get(current_year-2)
            status={'reference':f'{current_year-1}-Q{quarter} vs {current_year-2}-Q{quarter}',
                    'status':'missing_verified_comparable','growth_percent':None,
                    'missing_years':[y for y in (current_year-1,current_year-2) if y not in samples]}
            if now and then:
                if now.get('unit')==then.get('unit') and basis(now)==basis(then) and then['value']>0:
                    value=(Decimal(str(now['value']))/Decimal(str(then['value']))-1)*100
                    status={'reference':status['reference'],'status':'verified',
                            'growth_percent':float(value.quantize(Decimal('0.1'),rounding=ROUND_HALF_UP)),
                            'unit':now['unit'],'revenue_basis':basis(now),
                            'source_urls':sorted({now['source_url'],then['source_url']}),
                            'observation_values':{str(current_year-1):now['value'],str(current_year-2):then['value']}}
                else:
                    status['status']='incomparable_basis'
            details[kind]=status
        out.append(details)
    return {'period':f'Q{quarter} {current_year}','companies':out,
            'definition':'Prior-year growth equals prior-year revenue / prior-prior-year revenue - 1. Only matching official quarter/YTD company, scope, unit and revenue basis.'}

def main():
    rows=json.loads((ROOT/'data/financial_observations.json').read_text(encoding='utf-8'))['observations']
    result=evidence(rows)
    target=ROOT/'data/prior_year_growth_coverage.json'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for row in result['companies']:
        print('PRIOR_YEAR_GROWTH',row['company'],row['quarter']['status'],row['ytd']['status'])

if __name__=='__main__':main()
