#!/usr/bin/env python3
"""Fail-closed integrity gate for the two newly onboarded insurers.

This does not certify nine-company financial parity. It prevents a partial
onboarding from silently becoming an unsupported financial claim.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {'insurance_revenue', 'insurance_service_result',
            'combined_ratio', 'loss_ratio', 'expense_ratio'}
COMPANIES = {'Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende',
             'Protector', 'Storebrand', 'KLP Skadeforsikring', 'Alm. Brand'}


def validate(extended, sources, calendar):
    errors = []
    registered = {item.get('company') for item in sources.get('sources', [])}
    errors += ['Missing official source registry: ' + name
               for name in sorted(COMPANIES - registered)]
    for name in ('KLP Skadeforsikring', 'Alm. Brand'):
        if name not in calendar:
            errors.append('Missing issuer calendar: ' + name)
    insurers = extended.get('insurers', {})
    alm = insurers.get('Alm. Brand', {})
    if alm.get('status')=='verified_official_pdf_reconciled':
        metrics=alm.get('metrics') or {}
        required_alm=REQUIRED|{'insurance_revenue_growth','return_on_equity',
                               'solvency_ratio','profit_before_tax'}
        forbidden={'investment_return','investment_return_ytd','finance_return',
                   'return_on_investments','investment_result_as_roe'}
        source=alm.get('source_url','')
        sha=alm.get('source_sha256','')
        pages=alm.get('source_pages') or {}
        if (alm.get('company')!='Alm. Brand' or (alm.get('year'),alm.get('quarter'))!=(2026,3)
            or alm.get('scope')!='group' or alm.get('currency')!='DKK'
            or alm.get('source_type')!='official_quarterly_report'
            or source!='https://attachment.news.eu.nasdaq.com/ab696c52809fdbebae74678c86c8f5a78'
            or len(sha)!=64 or any(char not in '0123456789abcdef' for char in sha)
            or not required_alm.issubset(metrics) or forbidden.intersection(metrics)):
            errors.append('Alm Brand PDF source, period, or KPI coverage invalid')
        else:
            if (any(type(metrics[k]) not in (int,float) or not math.isfinite(metrics[k])
                    for k in required_alm)
                or any(type(pages.get(k)) is not int or pages[k]<=0 for k in required_alm)
                or not 0<metrics['return_on_equity']<100
                or not 100<=metrics['solvency_ratio']<=500
                or abs(metrics['loss_ratio']+metrics['expense_ratio']-metrics['combined_ratio'])>0.15):
                errors.append('Alm Brand quarterly PDF values or page provenance invalid')
            if (alm.get('return_on_equity_source_page')!=pages.get('return_on_equity')
                or 'equity' not in alm.get('return_on_equity_definition','').lower()
                or type(alm.get('return_on_equity_ytd')) not in (int,float)):
                errors.append('Alm Brand ROE requires explicitly issuer-reported equity return')
            growth=alm.get('revenue_growth_evidence') or {}
            if growth.get('source_sha256')!=sha or growth.get('source_page')!=pages.get('insurance_revenue'):
                errors.append('Alm Brand prior-year revenue evidence invalid')
            else:
                for mode in ('quarter','ytd'):
                    g=growth.get(mode,{})
                    if (type(g.get('current')) not in (int,float)
                        or type(g.get('prior_year')) not in (int,float)
                        or g['prior_year']<=0):
                        errors.append('Alm Brand prior-year growth comparator missing: '+mode)
                        continue
                    computed=(g['current']/g['prior_year']-1)*100
                    reported=(g.get('issuer_reported_growth_percent') if mode=='quarter'
                              else g.get('growth_percent'))
                    if type(reported) not in (int,float) or abs(computed-reported)>0.20:
                        errors.append('Alm Brand income growth mismatch: '+mode)
            for k in ('combined_ratio','loss_ratio','expense_ratio'):
                actual=alm.get('quarter_recalculated_ratios',{}).get(k)
                ytd=alm.get('reported_ytd_ratios',{}).get(k)
                computed=alm.get('ytd_recalculated_ratios',{}).get(k)
                if (type(actual) not in (int,float) or abs(actual-metrics[k])>0.20
                    or type(ytd) not in (int,float) or type(computed) not in (int,float)
                    or abs(computed-ytd)>0.20):
                    errors.append('Alm Brand quarter or HIÅ ratio reconciliation incomplete: '+k)
    else:
        if alm.get('status') != 'verified_issuer_announcement':
            errors.append('Alm. Brand must retain its announcement-only evidence status')
        if alm.get('source_type') != 'official_issuer_interim_announcement':
            errors.append('Alm. Brand source type must not claim PDF verification')
        if not str(alm.get('source_url', '')).startswith('https://investorrelations.almbrand.dk/'):
            errors.append('Alm. Brand official source URL missing')
        if alm.get('year') != 2026 or alm.get('quarter') != 3:
            errors.append('Alm. Brand verified snapshot is not Q3 2026')
        metrics = alm.get('metrics', {})
        if not REQUIRED.issubset(metrics) or not set(metrics).issubset(REQUIRED|{'insurance_revenue_growth'}) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in metrics.values()
        ) or ('insurance_revenue_growth' in metrics and abs(metrics['insurance_revenue_growth']-1.6)>0.001):
            errors.append('Alm. Brand verified metric set is incomplete or invalid')
    klp = insurers.get('KLP Skadeforsikring', {})
    if klp.get('status') == 'awaiting_source_verified_metrics' and klp.get('metrics') == {}:
        pass
    elif klp.get('status') == 'verified_official_pdf_reconciled':
        periods=klp.get('periods',[])
        if len(periods)!=3 or [(p.get('year'),p.get('quarter')) for p in periods]!=[(2026,1),(2026,2),(2026,3)]:
            errors.append('KLP must provide all three verified quarter PDF periods')
        else:
            for p in periods:
                metrics=p.get('metrics',{})
                if (p.get('status')!='verified_official_pdf_reconciled'
                    or not REQUIRED.issubset(metrics)
                    or not {'insurance_revenue_growth','solvency_ratio','profit_before_tax'}.issubset(metrics)
                    or any(type(metrics[k]) not in (float,int) or not math.isfinite(metrics[k]) for k in REQUIRED|{'insurance_revenue_growth','solvency_ratio','profit_before_tax'})
                    or 'return_on_equity' in metrics
                    or p.get('scope')!='company' or p.get('currency')!='NOK'
                    or p.get('source_type')!='official_quarterly_report'
                    or not str(p.get('source_url','')).startswith('https://www.klp.no/')
                    or len(str(p.get('source_sha256','')))!=64
                    or not p.get('source_pages',{}).get('quarter')
                    or not p.get('source_pages',{}).get('ytd')
                    or set(p.get('reported_ytd_ratios',{}))!=
                       {'gross_loss_ratio','reinsurance_ratio','loss_ratio','expense_ratio','combined_ratio'}):
                    errors.append('KLP PDF source or quarter metrics incomplete: Q'+str(p.get('quarter')))

                growth=p.get('revenue_growth_evidence',{})
                for period_kind in ('quarter','ytd'):
                    evidence=growth.get(period_kind,{})
                    current=evidence.get('current')
                    previous=evidence.get('prior_year')
                    claimed=evidence.get('growth_percent')
                    if (type(current) not in (int,float) or type(previous) not in (int,float)
                        or type(claimed) not in (int,float) or previous<=0
                        or not all(math.isfinite(x) for x in (current,previous,claimed))
                        or abs((current/previous-1)*100-claimed)>1e-6
                        or type(evidence.get('source_page')) is not int
                        or evidence['source_page']<1):
                        errors.append('KLP income growth lacks same-period prior-year PDF evidence Q'+str(p.get('quarter'))+' '+period_kind)
                management=p.get('management_kpi_evidence',{})
                if (management.get('source_sha256')!=p.get('source_sha256')
                    or type(management.get('source_page')) is not int
                    or management.get('source_page',0)<1
                    or management.get('source_metric')!='reported_solvency_and_pre_tax_profit'
                    or 'return_on_equity' in metrics
                    or management.get('period_basis',{}).get('solvency_ratio')!='quarter_end'
                    ):
                    errors.append('KLP solvency and pre-tax profit source evidence incomplete Q'+str(p.get('quarter')))
                if growth.get('previous_year')!=2025 or growth.get('source_sha256')!=p.get('source_sha256'):
                    errors.append('KLP income-growth evidence source mismatch Q'+str(p.get('quarter')))
                if abs(float(metrics.get('insurance_revenue_growth',-10000))-float(growth.get('quarter',{}).get('growth_percent',-20000)))>1e-6:
                    errors.append('KLP published income growth differs from source-backed quarter growth')

            if (klp.get('year'),klp.get('quarter'))!=(2026,3) or klp.get('metrics')!=periods[-1]['metrics']:
                errors.append('KLP latest published quarter does not match verified Q3')
    else:
        errors.append('KLP metrics require source verification before publication')
    return errors


def main():
    extended = json.loads((ROOT / 'data/extended_insurer_financials.json').read_text())
    sources = json.loads((ROOT / 'data/report_sources.json').read_text())
    calendar = json.loads((ROOT / 'data/calendar.json').read_text())
    errors = validate(extended, sources, calendar)
    print(json.dumps({'nine_issuer_registry_checked': True,
                      'nine_company_financial_parity_certified': False,
                      'klp_metrics_verified': extended.get('insurers',{}).get('KLP Skadeforsikring',{}).get('status')=='verified_official_pdf_reconciled',
                      'alm_brand_pdf_page_import_verified': extended.get('insurers',{}).get('Alm. Brand',{}).get('status')=='verified_official_pdf_reconciled',
                      'errors': errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
