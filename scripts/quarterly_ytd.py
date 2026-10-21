"""Automatic Tryg Norway YTD derived from complete isolated Excel quarters."""
ADDITIVE={'insurance_revenue','insurance_service_result'}
RATIOS={'combined_ratio','loss_ratio','expense_ratio'}
def derive_ytd(observations,year,through_quarter,company='Tryg',scope='norway'):
    if not 1 <= through_quarter <= 4: raise ValueError('Invalid quarter')
    output={}
    for metric in sorted(ADDITIVE | RATIOS):
        matching=[r for r in observations if r.get('company')==company and r.get('scope')==scope and r.get('year')==year and r.get('metric')==metric and r.get('period_type')=='quarter']
        byq={}
        for r in matching:
            q=r['quarter']
            if q in byq and abs(byq[q]['value']-r['value'])>1e-7:
                raise ValueError('Conflicting isolated quarters')
            byq[q]=r
        needed=list(range(1,through_quarter+1))
        if not all(q in byq for q in needed):continue
        units={byq[q].get('unit') for q in needed}
        if len(units)!=1:raise ValueError('Mixed units')
        if metric in ADDITIVE:
            value=sum(byq[q]['value'] for q in needed)
            method='sum_of_isolated_quarters'
        else:
            rev={r['quarter']:r for r in observations if r.get('company')==company and r.get('scope')==scope and r.get('year')==year and r.get('metric')=='insurance_revenue' and r.get('period_type')=='quarter'}
            if not all(q in rev for q in needed):continue
            denominator=sum(rev[q]['value'] for q in needed)
            if denominator<=0:raise ValueError('Nonpositive revenue denominator')
            value=sum(byq[q]['value']*rev[q]['value'] for q in needed)/denominator
            method='insurance_revenue_weighted_ratio'
        output[metric]={'value':round(value,6),'unit':next(iter(units)),'method':method,'quarters':needed}
    # Tryg reports combined ratio as loss ratio + expense ratio. Check for drift.
    if all(k in output for k in ('combined_ratio','loss_ratio','expense_ratio')):
        drift=abs(output['combined_ratio']['value']-output['loss_ratio']['value']-output['expense_ratio']['value'])
        if drift>0.15:raise ValueError('YTD combined ratio inconsistent with loss and expense ratios')
    return output

def add_tryg_ytd(observations):
    """Recalculate Tryg YTD after each new Excel import, replacing stale derived rows."""
    base=[r for r in observations if not (r.get('company')=='Tryg' and r.get('scope')=='norway' and r.get('period_type')=='ytd' and r.get('calculation') in ('sum_of_complete_quarters','sum_of_isolated_quarters','insurance_revenue_weighted_ratio'))]
    source=[r for r in base if r.get('company')=='Tryg' and r.get('scope')=='norway' and r.get('period_type')=='quarter' and r.get('source_sheet')]
    for year in sorted({r['year'] for r in source}):
        for q in range(1,5):
            for metric,derived in derive_ytd(source,year,q).items():
                parts=[next(r for r in source if r['year']==year and r['quarter']==k and r['metric']==metric) for k in derived['quarters']]
                row={k:v for k,v in parts[-1].items() if k not in ('value','quarter','source_cell','calculation')}
                row.update(quarter=q,period_type='ytd',metric=metric,value=derived['value'],unit=derived['unit'],calculation=derived['method'],source_cell=','.join(r.get('source_cell','') for r in parts),inputs=[{'quarter':r['quarter'],'value':r['value'],'source_cell':r.get('source_cell')} for r in parts])
                if any(r.get('company')=='Tryg' and r.get('scope')=='norway' and r.get('year')==year and r.get('quarter')==q and r.get('metric')==metric and r.get('period_type')=='ytd' for r in base):continue
                base.append(row)
    return base
