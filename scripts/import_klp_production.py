#!/usr/bin/env python3
"""KLP official-PDF quarterly importer. Fail closed without issuer ratio concordance.

This importer is additive: no replacement of existing seven-insurer feed, and
no use of HIÅ subtraction for KLP isolated quarter amounts.
"""
import json
from pathlib import Path
from import_extended_pdfs import INDEX
from klp_q1_2026_pdf_reconcile import run as run_q1
from klp_q2_q3_discovery import run as discover
from klp_q2q3_reconcile import run as run_later

REQUIRED=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio','insurance_revenue_growth')
KLP='KLP Skadeforsikring'
ARCHIVE=INDEX[KLP]

def row_from_reconciliation(item):
    q=item['quarter']
    if item.get('year')!=2026 or q not in (1,2,3):
        raise ValueError('Unexpected issuer period')
    if item.get('status') not in ('q1_2026_pdf_reconciled_not_published',
                                'issuer_pdf_quarter_and_ytd_reconciled_not_published'):
        raise ValueError('KLP not PDF ratio reconciled')
    docs=item.get('source_documents',[])
    if len(docs)!=2 or docs[0]['source_sha256']!=docs[1]['source_sha256']:
        raise ValueError('Quarter and HIÅ source fingerprints differ')
    if any(not d.get('source_pages') or not d.get('source_url','').startswith('https://www.klp.no/')
           or len(d.get('source_sha256',''))!=64 for d in docs):
        raise ValueError('Missing official KLP PDF provenance')
    values=item['reported_quarter_amounts']
    ratios=item['ratios']
    prior=item.get('reported_prior_year_quarter_amounts',{})
    ytd=item.get('reported_ytd_amounts') or values
    prior_ytd=item.get('reported_prior_year_ytd_amounts',{})
    if not all(k in x for x in (values,prior,ytd,prior_ytd) for k in ('insurance_revenue',)):
        raise ValueError('Missing same-basis KLP prior-year revenue comparator')
    def growth(current,previous):
        if not isinstance(current,(float,int)) or not isinstance(previous,(float,int)) or previous<=0:
            raise ValueError('Invalid source-backed KLP insurance revenue growth comparator')
        return (current/previous-1)*100
    quarter_growth=growth(values['insurance_revenue'],prior['insurance_revenue'])
    ytd_growth=growth(ytd['insurance_revenue'],prior_ytd['insurance_revenue'])
    management=item.get('reported_management_metrics') or {}
    for field in ('solvency_ratio','profit_before_tax','source_page'):
        if field not in management:
            raise ValueError('Missing issuer-reported additional KLP KPI: '+field)
    metrics={'insurance_revenue':values['insurance_revenue'],
             'insurance_service_result':values['insurance_service_result'],
             'combined_ratio':ratios['combined_ratio'],
             'loss_ratio':ratios['loss_ratio'],
             'expense_ratio':ratios['expense_ratio'],
             'insurance_revenue_growth':quarter_growth,
             'solvency_ratio':management['solvency_ratio'],
             'profit_before_tax':management['profit_before_tax']}
    if not set(REQUIRED).issubset(metrics) or metrics['insurance_revenue']<=0:
        raise ValueError('Incomplete KLP issuer metrics')
    return {'company':KLP,'year':2026,'quarter':q,'scope':'company',
            'currency':'NOK','unit':'NOK million for financial amounts; percent for ratios',
            'source_type':'official_quarterly_report',
            'source_url':docs[0]['source_url'],
            'source_sha256':docs[0]['source_sha256'],
            'source_pages':{'quarter':docs[0]['source_pages'],
                            'ytd':docs[1]['source_pages']},
            'metrics':metrics,'reported_ytd_ratios':item['reported_ytd_ratios'],
            'management_kpi_evidence':{'source_page':management['source_page'],
                'source_sha256':docs[0]['source_sha256'],
                'period_basis':management['period_basis'],
                'profit_before_tax_ytd':management['profit_before_tax_ytd'],
                'source_metric':'reported_solvency_and_pre_tax_profit'},
            'revenue_growth_evidence':{
                'quarter':{'year':2026,'quarter':q,'current':values['insurance_revenue'],
                           'prior_year':prior['insurance_revenue'],'growth_percent':quarter_growth,
                           'source_page':docs[0]['source_pages'][0]},
                'ytd':{'year':2026,'quarter':q,'current':ytd['insurance_revenue'],
                       'prior_year':prior_ytd['insurance_revenue'],'growth_percent':ytd_growth,
                       'source_page':docs[0]['source_pages'][0]},
                'revenue_definition':'KLP Forsikringsinntekter; NOK million; same company basis',
                'previous_year':2025,
                'source_sha256':docs[0]['source_sha256']},
            'status':'verified_official_pdf_reconciled'}

def build_snapshot(q1,q2,q3):
    rows=[row_from_reconciliation(x) for x in (q1,q2,q3)]
    if [(r['year'],r['quarter']) for r in rows]!=[(2026,1),(2026,2),(2026,3)]:
        raise ValueError('KLP Q1-Q3 incomplete or out of order')
    return {'company':KLP,'status':'verified_official_pdf_reconciled',
            'year':2026,'quarter':3,'scope':'company','currency':'NOK',
            'source_type':'official_quarterly_report','source_url':rows[-1]['source_url'],
            'source_sha256':rows[-1]['source_sha256'],
            'source_pages':rows[-1]['source_pages'],
            'metrics':rows[-1]['metrics'],
            'periods':rows,'report_archive':ARCHIVE}

def verify_latest(existing,new):
    if not existing:return
    if existing.get('status')=='awaiting_source_verified_metrics' and existing.get('metrics')=={}:
        return
    if existing.get('status')!='verified_official_pdf_reconciled':
        raise ValueError('Unrecognized previous KLP evidence')
    if (existing.get('year'),existing.get('quarter'))>(new['year'],new['quarter']):
        raise ValueError('Refusing rollback of KLP quarter')
    previous={(p['year'],p['quarter']):p for p in existing.get('periods',[])}
    for item in new['periods']:
        key=item['year'],item['quarter']
        if key in previous and previous[key]!=item:
            raise ValueError('Previously approved KLP evidence changed; manual review required')

def update(root, q1=None, q2=None, q3=None):
    root=Path(root)
    path=root/'data/extended_insurer_financials.json'
    current=json.loads(path.read_text(encoding='utf-8'))
    if any(x is None for x in (q1,q2,q3)):
        q1=run_q1()
        discovered=discover()
        if discovered.get('missing'):
            raise ValueError('KLP Q2/Q3 issuer PDF missing')
        q2=run_later(discovered['periods']['2']['url'],2)
        q3=run_later(discovered['periods']['3']['url'],3)
        for q,item in [(2,q2),(3,q3)]:
            if item['source_documents'][0]['source_sha256']!=discovered['periods'][str(q)]['sha256']:
                raise ValueError('KLP PDF changed between discovery and reconciliation')
    snapshot=build_snapshot(q1,q2,q3)
    verify_latest(current.get('insurers',{}).get(KLP),snapshot)
    if current['insurers'].get(KLP)==snapshot:return False
    current['insurers'][KLP]=snapshot
    path.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return True

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print('KLP_PRODUCTION_PDF_IMPORT',update(root))
