#!/usr/bin/env python3
"""Supplement legacy extended issuer snapshots with complete HIÅ provenance.

Rolling periods already contain their own HIÅ metrics; do not rewrite
historical snapshots or change the quarter figures to fill a YTD gap.
"""
import hashlib
import json
import math
import re
from pathlib import Path
from import_extended_pdfs import download,pages
from rolling_klp_reports import verify_report
from publish_geographic_workbooks import atomic_write

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/extended_insurer_financials.json'
KLP='KLP Skadeforsikring'
ALM='Alm. Brand'
FIELDS={'insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio','insurance_revenue_growth','return_on_equity','solvency_ratio','profit_before_tax'}

def finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def make_klp(item,reconciled):
    row=item['periods'][-1]
    if (reconciled['year'],reconciled['quarter'])!=(item['year'],item['quarter']):
        raise ValueError('KLP HIÅ period mismatch')
    from import_klp_production import row_from_reconciliation
    fresh=row_from_reconciliation(reconciled)
    if fresh['metrics']!=row['metrics'] or fresh['source_sha256']!=row['source_sha256']:
        raise ValueError('KLP HIÅ report disagrees with previously verified quarter')
    management=reconciled['reported_management_metrics'];amounts=reconciled['reported_ytd_amounts']
    prior=reconciled['reported_prior_year_ytd_amounts'];ratios=reconciled['reported_ytd_ratios']
    metrics={'insurance_revenue':amounts['insurance_revenue'],'insurance_service_result':amounts['insurance_service_result'],
        'insurance_revenue_growth':(amounts['insurance_revenue']/prior['insurance_revenue']-1)*100,
        'profit_before_tax':management['profit_before_tax_ytd'],'solvency_ratio':management['solvency_ratio'],
        **{k:ratios[k] for k in ('combined_ratio','loss_ratio','expense_ratio')}}
    return dict(year=item['year'],quarter=item['quarter'],scope='company',currency='NOK',
        source_type='official_quarterly_report',source_url=row['source_url'],source_sha256=row['source_sha256'],
        metrics=metrics,source_pages={k:row['source_pages']['ytd'][-1] if k in ('combined_ratio','loss_ratio','expense_ratio','solvency_ratio') else row['source_pages']['quarter'][0] for k in metrics},
        current_revenue=amounts['insurance_revenue'],prior_revenue=prior['insurance_revenue'])

def make_alm(item,pdf):
    ev=item['supplemental_pdf_evidence'];metrics=pdf['ytd_metrics']
    if (pdf['year'],pdf['quarter'])!=(item['year'],item['quarter']) or pdf['source_sha256']!=ev['source_sha256'] or pdf['source_url']!=ev['source_url']:
        raise ValueError('Alm. Brand HIÅ PDF differs from verified supplemental report')
    growth=pdf['revenue_growth_evidence']['ytd']
    return dict(year=item['year'],quarter=item['quarter'],scope='group',currency='DKK',
        source_type='official_quarterly_report',source_url=pdf['source_url'],source_sha256=pdf['source_sha256'],
        metrics=metrics,source_pages=pdf['source_pages'],current_revenue=growth['current'],prior_revenue=growth['prior_year'])

def validate_baseline(item):
    ev=item.get('ytd_pdf_evidence')
    if ev is None:return [] # old source fixtures and unpublished snapshots
    if not isinstance(ev,dict):return ['Extended HIÅ evidence not an object']
    c=item.get('company');expected=FIELDS-({'return_on_equity'} if c==KLP else set())
    metrics=ev.get('metrics',{});pages_=ev.get('source_pages',{});prior=ev.get('prior_revenue')
    if ((ev.get('year'),ev.get('quarter'))!=(item.get('year'),item.get('quarter'))
        or ev.get('scope')!=item.get('scope') or ev.get('currency')!=item.get('currency')
        or ev.get('source_type')!='official_quarterly_report' or not str(ev.get('source_url','')).startswith('https://')
        or not re.fullmatch(r'[0-9a-f]{64}',str(ev.get('source_sha256','')))
        or set(metrics)!=expected or not all(finite(v) for v in metrics.values())
        or set(pages_)!=expected or any(type(p) is not int or p<1 for p in pages_.values())
        or not finite(prior) or prior<=0 or ev.get('current_revenue')!=metrics.get('insurance_revenue')
        or metrics.get('solvency_ratio')!=item.get('metrics',{}).get('solvency_ratio')):
        return [str(c)+' invalid period-matched HIÅ evidence']
    if abs((metrics['insurance_revenue']/prior-1)*100-metrics['insurance_revenue_growth'])>1e-6:
        return [str(c)+' HIÅ revenue growth fails source arithmetic']
    if abs(metrics['combined_ratio']-metrics['loss_ratio']-metrics['expense_ratio'])>0.21:
        return [str(c)+' HIÅ ratio components disagree']
    if c==KLP:
        row=item['periods'][-1];growth=row['revenue_growth_evidence']['ytd']
        if (ev['source_url']!=row['source_url'] or ev['source_sha256']!=row['source_sha256']
            or metrics['insurance_revenue']!=growth['current'] or prior!=growth['prior_year']
            or metrics['profit_before_tax']!=row['management_kpi_evidence']['profit_before_tax_ytd']
            or any(metrics[k]!=row['reported_ytd_ratios'][k] for k in ('combined_ratio','loss_ratio','expense_ratio'))):
            return ['KLP HIÅ values disagree with approved period source']
    elif c==ALM:
        supplemental=item.get('supplemental_pdf_evidence',{})
        if (ev['source_url']!=supplemental.get('source_url') or ev['source_sha256']!=supplemental.get('source_sha256')
            or any(metrics[k]!=supplemental.get('metrics',{}).get(k,{}).get('ytd_value') for k in ('return_on_equity','profit_before_tax'))):
            return ['Alm. Brand HIÅ values disagree with approved supplemental source']
    else:return ['Unknown extended HIÅ issuer']
    return []

def run(path=DATA):
    data=json.loads(path.read_text(encoding='utf-8'))
    item=data['insurers'][KLP]
    if item.get('ytd_metrics') or item.get('ytd_pdf_evidence'):
        errors=validate_baseline(item)
        if errors:raise ValueError('; '.join(errors))
        return False
    if item.get('status')!='verified_official_pdf_reconciled':return False
    raw=download(item['source_url'],KLP)
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=item['source_sha256']:raise ValueError('KLP original source changed; HIÅ refresh blocked')
    report=verify_report(pages(raw),item['year'],item['quarter'],item['source_url'],digest)
    item['ytd_pdf_evidence']=make_klp(item,report)
    errors=validate_baseline(item)
    if errors:raise ValueError('; '.join(errors))
    atomic_write(path,data)
    print('KLP_BASELINE_YTD_VERIFIED',item['ytd_pdf_evidence']['metrics'],flush=True)
    return True

if __name__=='__main__':run()
