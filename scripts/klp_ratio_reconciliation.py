#!/usr/bin/env python3
"""Fail-closed KLP quarter ratio verification against issuer HIÅ KPI definitions.

KLP reports gross claims ratio, reinsurance ratio, net claims ratio, cost ratio
and total claims ratio. Quarter amounts come from its quarter result column;
HIÅ is used ONLY to verify the same definitions and sign conventions.
"""
from decimal import Decimal
from klp_quarter_from_ytd import number

METRICS=('loss_ratio','expense_ratio','combined_ratio')
SOURCE_FIELDS=('source_url','source_sha256','source_pages')
REQUIRED=('insurance_revenue','gross_claims_cost','reinsurance_effect','operating_expenses')

def ratios(amounts):
    if set(amounts) != set(REQUIRED):
        raise ValueError('Missing KLP issuer-defined ratio components')
    a={key:number(amounts[key]) for key in REQUIRED}
    if a['insurance_revenue']<=0:
        raise ValueError('Nonpositive insurance revenue')
    revenue=a['insurance_revenue']
    gross=a['gross_claims_cost']/revenue*100
    reinsurance=a['reinsurance_effect']/revenue*100
    net=gross+reinsurance
    expense=a['operating_expenses']/revenue*100
    return {'gross_loss_ratio':gross,'reinsurance_ratio':reinsurance,
            'loss_ratio':net,'expense_ratio':expense,
            'combined_ratio':net+expense}

def reconcile(quarter, ytd, tolerance='0.15'):
    """Only return quarter KPIs if the HIÅ definition reproduces reported HIÅ ratios.

    Inputs are extracted source evidence, not guessed values. Reinsurance effect
    is signed consistently with KLP's published reinsurance ratio.
    """
    if quarter.get('period_type')!='quarter' or ytd.get('period_type')!='ytd':
        raise ValueError('Quarter and HIÅ source columns must be explicit')
    for item in (quarter,ytd):
        if item.get('company')!='KLP Skadeforsikring' or not all(item.get(k) for k in SOURCE_FIELDS):
            raise ValueError('Missing official KLP PDF evidence')
        if not isinstance(item.get('source_pages'),list) or not all(type(p)==int and p>0 for p in item['source_pages']):
            raise ValueError('Invalid PDF page references')
        if len(item['source_sha256'])!=64 or any(c not in '0123456789abcdef' for c in item['source_sha256']):
            raise ValueError('Invalid PDF SHA-256')
        if not item['source_url'].startswith('https://www.klp.no/'):
            raise ValueError('Unapproved KLP source')
        if not item.get('issuer_definition_verified'):
            raise ValueError('Issuer KPI definition not verified')
    for key in ('year','quarter','scope','currency','unit'):
        if quarter.get(key)!=ytd.get(key) or quarter.get(key) is None:
            raise ValueError('Quarter/HIÅ reporting basis mismatch')
    q=ratios(quarter.get('ratio_components') or {})
    cumulative=ratios(ytd.get('ratio_components') or {})
    published=ytd.get('reported_ratios') or {}
    if set(published)!=set(cumulative):
        raise ValueError('Incomplete published HIÅ ratio evidence')
    for key in cumulative:
        if abs(cumulative[key]-number(published[key]))>number(tolerance):
            raise ValueError('HIÅ issuer-ratio reconciliation failed: '+key)
    return {'company':'KLP Skadeforsikring','year':quarter['year'],
            'quarter':quarter['quarter'],'period_type':'quarter',
            'ratios':{k:float(q[k]) for k in METRICS},
            'gross_loss_ratio':float(q['gross_loss_ratio']),
            'reinsurance_ratio':float(q['reinsurance_ratio']),
            'source_documents':[{k:item[k] for k in SOURCE_FIELDS} for item in (quarter,ytd)],
            'status':'quarter_ratios_reconciled_to_issuer_ytd_method'}
