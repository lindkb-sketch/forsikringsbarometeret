"""Presentation extraction for observed issuer layouts, with no target-value searching.

Unknown or ambiguous layouts yield no evidence. Quarterly, YTD and point-in-time
metrics are never conflated with forecasts, TTM or underlying segment measures.
"""
import re
from decimal import Decimal
from math import isfinite

NUM=r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
KEYS={'Insurance revenue':'insurance_revenue','Insurance revenue, net':'insurance_revenue',
      'Insurance service result':'insurance_service_result','Underwriting result':'insurance_service_result',
      'Pre-tax profit':'profit_before_tax','Profit before taxes':'profit_before_tax',
      'Claims ratio':'loss_ratio','Risk ratio, %':'loss_ratio','Expense ratio':'expense_ratio',
      'Cost ratio, %':'expense_ratio','Combined ratio':'combined_ratio','Combined ratio, %':'combined_ratio',
      'Solvency ratio':'solvency_ratio','Solvency II ratio,%':'solvency_ratio'}
AMOUNTS={'insurance_revenue','insurance_service_result','profit_before_tax'}

def extract(company,texts,y,q):
    evidence=[]
    def add(page,label,metric,value,period,unit,method):
        value=float(value.replace(',','')) if isinstance(value,str) else float(value)
        if isfinite(value):
            evidence.append(dict(metric=metric,period_type=period,scope='group',unit=unit,value=value,
                                 source_page=page,source_label=label,extraction_method=method))
    def row(lines,label,count):
        rows=[l for l in lines if re.fullmatch(re.escape(label)+rf' (?:{NUM})(?: (?:{NUM})){{{count-1}}}',l)]
        if len(rows)!=1:return None
        return rows[0][len(label)+1:].split()
    for page,t in enumerate(texts,1):
        lines=[' '.join(l.replace('–','-').replace('−','-').split()) for l in t.splitlines()]
        if company=='Tryg':
            title=f'Reported figures Q{q} {y} and Consensus {y}-{y+2}'
            head=f'Q{q} {y} Q{q} {y} {y} {y+1} {y+2}'
            if title in lines and head in lines and 'DKKm Reported Consensus Consensus Consensus Consensus' in lines:
                for label in ('Insurance revenue','Insurance service result','Pre-tax profit','Claims ratio','Expense ratio','Combined ratio','Solvency ratio'):
                    v=row(lines,label,5)
                    if v:
                        metric=KEYS[label];add(page,label,metric,v[0],'quarter','MDKK' if metric in AMOUNTS else 'percent','explicit_reported_column_not_consensus')
            if f'Financial highlights Q{q} {y}' in lines:
                text=' '.join(lines)
                vals=re.findall(rf'\(return on own funds\) was ({NUM})% in Q{q}\b',text,re.I)
                if len(vals)==1:add(page,'ROOF','return_on_equity',vals[0],'quarter','percent','explicit_current_quarter_issuer_statement')
        elif company=='Sampo':
            # Exact period labels are resolved before looking at any values.
            # Historical comparatives and different segments are excluded.
            if 'Group: results and key figures' in lines:
                headers=[l.split()[1:] for l in lines if l.startswith('EURm ') and f'Q{q}/{y}' in l]
                if len(headers)==1:
                    cols=re.findall(r'(?:1-\d{1,2}/20\d{2}|Q[1-4]/20\d{2}|FY 20\d{2})',' '.join(headers[0]))
                    if ' '.join(cols)==' '.join(headers[0]) and cols.count(f'Q{q}/{y}')==1:
                        for label in ('Insurance revenue, net','Underwriting result','Profit before taxes','Risk ratio, %','Cost ratio, %','Combined ratio, %'):
                            v=row(lines,label,len(cols))
                            if not v:continue
                            metric=KEYS[label];unit='EURm' if metric in AMOUNTS else 'percent'
                            for period,column in [('quarter',f'Q{q}/{y}'),('ytd',f'1-{3*q}/{y}' if q<4 else f'FY {y}')]:
                                if cols.count(column)==1:add(page,label,metric,v[cols.index(column)],period,unit,'explicit_group_period_column')
            if 'Solvency II SCR and own funds' in lines:
                headers=[l for l in lines if l.startswith('EURm ') and f'Q{q}/{y}' in l]
                if len(headers)==1:
                    cols=re.findall(r'(?:Q[1-4]/20\d{2}|FY 20\d{2})',headers[0][5:])
                    if ' '.join(cols)==headers[0][5:] and cols.count(f'Q{q}/{y}')==1:
                        v=row(lines,'Solvency II ratio,%',len(cols))
                        if v:add(page,'Solvency II ratio','solvency_ratio',v[cols.index(f'Q{q}/{y}')],'quarter','percent','explicit_group_solvency_period_column')
        elif company=='Storebrand':
            # Do not read TTM combined ratio or annualised ROE from chart positions.
            if f'Solvency position and sensitivities Q{q} {y}' in lines and 'Storebrand Group' in lines:
                vals=re.findall(rf'SII-margin Q{q} ({NUM})%', ' '.join(lines))
                if len(vals)==1:
                    for period in ('quarter','ytd'):
                        add(page,'SII-margin','solvency_ratio',vals[0],period,'percent','explicit_group_period_end_point')
    # Multiple inconsistent extracts are not silently resolved.
    grouped={}
    for e in evidence:grouped.setdefault((e['metric'],e['period_type'],e['unit']),[]).append(e)
    return [v[0] for v in grouped.values() if len({e['value'] for e in v})==1]

def reconcile(company,y,q,feed,report_docs,presentation,texts):
    """Compare independently extracted presentation values with fingerprint-rechecked report observations."""
    result=[]
    for p in extract(company,texts,y,q):
        candidates=[r for r in feed.get('observations',[]) if
                    (r.get('company'),r.get('year'),r.get('quarter'),r.get('scope'),
                     r.get('metric'),r.get('period_type'),r.get('unit'))==
                    (company,y,q,'group',p['metric'],p['period_type'],p['unit']) and
                    any(d['expected_fingerprint_matches'] and d['source_sha256']==r.get('source_sha256')
                        and d['requested_url']==r.get('source_url') and d['source_sha256']!=presentation['source_sha256']
                        for d in report_docs)]
        if len(candidates)!=1:continue
        r=candidates[0]
        delta=abs(Decimal(str(r['value']))-Decimal(str(p['value'])))
        # Same reported precision, no broad numerical tolerance.
        result.append(dict(metric=p['metric'],period_type=p['period_type'],scope='group',unit=p['unit'],
                           status='match' if delta==0 else 'conflict',value=p['value'],report_value=r['value'],
                           method='independent_presentation_extraction_and_report_fingerprint_recheck',
                           report={k:r[k] for k in ('source_url','source_sha256','source_page')},
                           presentation=dict(source_url=presentation['url'],source_sha256=presentation['source_sha256'],
                                             source_page=p['source_page'],source_label=p['source_label'],extraction_method=p['extraction_method'])))
    return result
