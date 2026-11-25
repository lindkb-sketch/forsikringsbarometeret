"""Period-matched nine-insurer HIÅ comparison and traceability."""
import math
import re
from prior_year_growth_coverage import basis as revenue_basis
from import_extended_ytd import validate_baseline

METRICS=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio',
         'insurance_revenue_growth','return_on_equity','solvency_ratio','profit_before_tax')

def finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def valid(row):
    return (row.get('status') in ('reported','calculated') and finite(row.get('value'))
        and str(row.get('source_url','')).startswith('https://')
        and type(row.get('source_page')) is int and row['source_page']>0
        and bool(re.fullmatch(r'[0-9a-f]{64}',str(row.get('source_sha256','')))))

def provenance(row,method='reported'):
    return {**{k:row.get(k) for k in ('source_url','source_sha256','source_page','source_definition','unit','year','quarter','period_type','value')},
            'method':method}

def group_values(observations,company,latest):
    if not latest:return {},{}
    year,q=latest
    rows=[r for r in observations if r.get('company')==company and r.get('scope')=='group' and valid(r)]
    def lookup(y,period,key):
        candidates=[r for r in rows if (r['year'],r['quarter'],r['period_type'],r['metric'])==(y,q,period,key)]
        if len(candidates)>1:raise ValueError(company+' ambiguous '+period+' '+key)
        return candidates[0] if candidates else None
    values={};sources={}
    for key in METRICS:
        row=lookup(year,'ytd',key)
        method='reported'
        if row and row.get('status')=='calculated':method='calculated'
        if key=='solvency_ratio':
            point=lookup(year,'quarter',key)
            if point and row and abs(point['value']-row['value'])>0.001:
                raise ValueError(company+' conflicting quarter-end solvency')
            row=row or point
            method='reported_quarter_end'
        elif q==1 and row is None:
            row=lookup(year,'quarter',key)
            method='q1_equals_ytd'
        if row:
            values[key]=row['value'];sources[key]=provenance(row,method)
    if 'insurance_revenue_growth' not in values:
        current=lookup(year,'ytd','insurance_revenue')
        previous=lookup(year-1,'ytd','insurance_revenue')
        if q==1:
            current=current or lookup(year,'quarter','insurance_revenue')
            previous=previous or lookup(year-1,'quarter','insurance_revenue')
        if current and previous and previous['value']>0 and current.get('unit')==previous.get('unit') and revenue_basis(current)==revenue_basis(previous):
            values['insurance_revenue_growth']=(current['value']/previous['value']-1)*100
            sources['insurance_revenue_growth']={**provenance(current,'calculated'),
                'source_definition':'Same-basis current HIÅ revenue / prior-year HIÅ revenue - 1',
                'value':values['insurance_revenue_growth'],'period_type':'ytd',
                'source_documents':[provenance(current),provenance(previous)]}
    return values,sources

def extended_values(item):
    if not item:return {},{}
    baseline=item.get('ytd_pdf_evidence')
    if baseline:
        errors=validate_baseline(item)
        if errors:raise ValueError('; '.join(errors))
        vals=baseline['metrics']
        ev={k:{'source_url':baseline['source_url'],'source_sha256':baseline['source_sha256'],
               'source_page':baseline['source_pages'][k],'year':baseline['year'],'quarter':baseline['quarter'],
               'period_type':'ytd','value':v,'method':'reported_quarter_end' if k=='solvency_ratio' else 'calculated' if k=='insurance_revenue_growth' else 'reported',
               'source_definition':'Verified issuer HIÅ PDF' if k!='solvency_ratio' else 'Reported balance-sheet date solvency'}
            for k,v in vals.items()}
        ev['insurance_revenue_growth']['inputs']={'current':baseline['current_revenue'],'prior_year':baseline['prior_revenue']}
        return vals,ev
    if not item.get('ytd_metrics'):return {},{}
    vals=item['ytd_metrics']
    page_map=item.get('source_pages',{})
    if item.get('company')=='KLP Skadeforsikring':
        # Full-year derived Q4 has an annual source; cumulative values
        # themselves come from that report (not from the Q4 subtraction).
        row=item['periods'][-1]
        if row.get('quarter_calculation'):
            doc=row['quarter_calculation']['annual']['document']
            page_map={k:doc['ratio_page'] if k.endswith('ratio') else doc['statement_page'] for k in vals}
        else:
            page_map={k:row['source_pages']['ytd'][-1] if k.endswith('ratio') else row['source_pages']['quarter'][0] for k in vals}
    ev={}
    for k,v in vals.items():
        p=page_map.get(k)
        if not finite(v) or type(p) is not int or p<1 or not re.fullmatch(r'[0-9a-f]{64}',str(item.get('source_sha256',''))) or not str(item.get('source_url','')).startswith('https://'):
            raise ValueError('Extended rolling HIÅ source missing: '+k)
        method='reported_quarter_end' if k=='solvency_ratio' else 'calculated' if k=='insurance_revenue_growth' else 'reported'
        if k=='combined_ratio' and item.get('quarter_calculation') and not item['quarter_calculation'].get('annual_combined_ratio_reported'):method='calculated'
        ev[k]={'source_url':item['source_url'],'source_sha256':item['source_sha256'],'source_page':p,
               'year':item['year'],'quarter':item['quarter'],'period_type':'ytd','value':v,'method':method,
               'source_definition':'Reported balance-sheet date solvency' if k=='solvency_ratio' else 'Issuer cumulative financial report'}
    if 'insurance_revenue_growth' in ev:
        if item.get('company')=='KLP Skadeforsikring':
            e=item['periods'][-1]['revenue_growth_evidence']['ytd']
            ev['insurance_revenue_growth']['inputs']={'current':e['current'],'prior_year':e['prior_year']}
        else:
            ev['insurance_revenue_growth']['inputs']={'current':vals['insurance_revenue'],'prior_year':item['growth_evidence']['ytd_prior']}
    return vals,ev

def build_for(company,period,observations,extended):
    if not period:return {},{}
    match=re.fullmatch(r'Q([1-4]) (20\d{2})',period)
    if not match:raise ValueError('Invalid comparison period')
    q,year=map(int,match.groups())
    item=extended.get(company)
    if item:
        if (item.get('year'),item.get('quarter'))!=(year,q):
            raise ValueError('Extended HIÅ comparison period mismatch')
        return extended_values(item)
    return group_values(observations,company,(year,q))
