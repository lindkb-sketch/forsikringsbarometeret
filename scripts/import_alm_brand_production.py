#!/usr/bin/env python3
"""Admit issuer-PDF-reconciled Alm. Brand Group quarterly metrics to production.

No unverified ROE/ROOF or investment-return proxies. Never downgrade or
overwrite an existing approved source with announcement-only data.
"""
import json
import math
from pathlib import Path
from alm_brand_live_pdf import run, trusted_pdf_link, OFFICIAL_FILING_PDF

COMPANY='Alm. Brand'
REQUIRED={'insurance_revenue','insurance_service_result','combined_ratio',
          'loss_ratio','expense_ratio','insurance_revenue_growth',
          'return_on_equity','solvency_ratio','profit_before_tax'}
FORBIDDEN={'investment_return','investment_return_ytd','finance_return',
           'return_on_investments','investment_result_as_roe'}

def validated_pdf(item):
    if (item.get('company')!=COMPANY or item.get('year')!=2026
        or item.get('quarter')!=3 or item.get('scope')!='group'
        or item.get('currency')!='DKK' or item.get('source_type')!='official_quarterly_report'
        or item.get('status')!='verified_official_pdf_reconciled'):
        raise ValueError('Alm Brand must have a verified Group 2026 Q3 official PDF')
    url=item.get('source_url','')
    if not trusted_pdf_link(url) or url!=OFFICIAL_FILING_PDF:
        raise ValueError('Unapproved official Q3 issuer filing source')
    sha=item.get('source_sha256','')
    if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Invalid PDF SHA256')
    values=item.get('metrics') or {}
    if not REQUIRED.issubset(values) or FORBIDDEN.intersection(values):
        raise ValueError('Incomplete or forbidden Alm Brand KPI coverage')
    if any(type(values[k]) not in (int,float) or not math.isfinite(values[k]) for k in REQUIRED):
        raise ValueError('Invalid issuer financial metric values')
    pages=item.get('source_pages') or {}
    if not all(type(pages.get(k)) is int and pages[k]>0 for k in REQUIRED):
        raise ValueError('Missing per-KPI PDF page evidence')
    if (abs(values['loss_ratio']+values['expense_ratio']-values['combined_ratio'])>0.15
        or values['insurance_revenue']<=0 or values['solvency_ratio']<100):
        raise ValueError('Inconsistent insurer KPI definitions')
    if (item.get('return_on_equity_ytd') is None
        or item.get('return_on_equity_definition','').lower().find('equity')<0
        or pages.get('return_on_equity')!=item.get('return_on_equity_source_page')):
        raise ValueError('Missing official ROE after-tax evidence')
    growth=item.get('revenue_growth_evidence',{})
    if growth.get('source_sha256')!=sha or growth.get('source_page')!=pages['insurance_revenue']:
        raise ValueError('Income-growth evidence differs from official PDF')
    for kind in ('quarter','ytd'):
        data=growth.get(kind,{})
        if not all(type(data.get(k)) in (int,float) for k in ('current','prior_year')):
            raise ValueError('Missing same-basis prior-year revenue values')
        if data['prior_year']<=0:raise ValueError('Invalid prior-year revenue')
        calc=(data['current']/data['prior_year']-1)*100
        reported=(data.get('issuer_reported_growth_percent') if kind=='quarter'
                  else data.get('growth_percent'))
        if type(reported) not in (float,int) or abs(calc-reported)>0.20:
            raise ValueError('Alm Brand growth mismatch: '+kind)
    if abs(values['insurance_revenue_growth']-growth['quarter']['issuer_reported_growth_percent'])>0.01:
        raise ValueError('Published revenue growth disagrees with issuer')
    for name in ('combined_ratio','loss_ratio','expense_ratio'):
        actual=item.get('quarter_recalculated_ratios',{}).get(name)
        if type(actual) not in (int,float) or abs(actual-values[name])>0.20:
            raise ValueError('Quarter issuer-ratio reconciliation not verified: '+name)
        ytd=item.get('reported_ytd_ratios',{}).get(name)
        recalculated=item.get('ytd_recalculated_ratios',{}).get(name)
        if type(ytd) not in (int,float) or type(recalculated) not in (int,float) or abs(ytd-recalculated)>0.20:
            raise ValueError('HIÅ issuer-ratio reconciliation not verified: '+name)
    return {
        'company':COMPANY,'year':2026,'quarter':3,'scope':'group','currency':'DKK',
        'source_type':'official_quarterly_report','source_url':url,'source_sha256':sha,
        'source_pages':pages,'metrics':{k:values[k] for k in sorted(REQUIRED)},
        'unit':'DKK million for financial amounts; percent for ratios',
        'status':'verified_official_pdf_reconciled',
        'reported_ytd_ratios':item['reported_ytd_ratios'],
        'quarter_recalculated_ratios':item['quarter_recalculated_ratios'],
        'ytd_recalculated_ratios':item['ytd_recalculated_ratios'],
        'revenue_growth_evidence':growth,
        'return_on_equity_definition':item['return_on_equity_definition'],
        'return_on_equity_ytd':item['return_on_equity_ytd'],
        'return_on_equity_source_page':item['return_on_equity_source_page'],
        'solvency_definition':item['solvency_definition'],
        'profit_before_tax_ytd':item['profit_before_tax_ytd'],
        'issuer_page_url':item['issuer_page_url']
    }

def update(root,report=None):
    root=Path(root)
    path=root/'data/extended_insurer_financials.json'
    previous=json.loads(path.read_text(encoding='utf-8'))
    doc=validated_pdf(run() if report is None else report)
    prior=previous.get('insurers',{}).get(COMPANY,{})
    if prior.get('status')=='verified_official_pdf_reconciled':
        if prior!=doc:
            raise ValueError('Approved Alm Brand PDF or financial observations changed; manual review required')
        return False
    if prior.get('status')!='verified_issuer_announcement':
        raise ValueError('Refusing to replace unexpected Alm Brand financial evidence')
    # The announcement is independent evidence; the PDF must agree exactly.
    for metric in ('insurance_revenue','insurance_service_result','combined_ratio',
                   'loss_ratio','expense_ratio','insurance_revenue_growth'):
        if abs(prior['metrics'][metric]-doc['metrics'][metric])>0.001:
            raise ValueError('Issuer announcement/PDF disagreement: '+metric)
    previous['insurers'][COMPANY]=doc
    path.write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return True

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print('ALM_BRAND_PRODUCTION_PDF_IMPORT',update(root))
