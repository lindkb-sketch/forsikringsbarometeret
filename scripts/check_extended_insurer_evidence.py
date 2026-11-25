#!/usr/bin/env python3
"""Fail-closed integrity gate for the two newly onboarded insurers.

This does not certify nine-company financial parity. It prevents a partial
onboarding from silently becoming an unsupported financial claim.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from import_alm_brand_supplemental import validate_supplemental

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
    if (alm.get('year',0),alm.get('quarter',0))>(2026,3):
        from rolling_alm_brand_reports import validate_rolling
        errors.extend(validate_rolling(alm))
    else:
        if alm.get('status') not in ('verified_issuer_announcement','verified_official_presentation_reconciled'):
            errors.append('Alm. Brand evidence status unsupported')
        if alm.get('status')=='verified_official_presentation_reconciled':
            from import_alm_brand_presentation import PRESENTATION, EXPECTED
            evidence=alm.get('presentation_evidence',{})
            if (evidence.get('source_type')!='official_results_presentation'
                or evidence.get('source_url')!=PRESENTATION
                or len(str(evidence.get('source_sha256','')))!=64
                or evidence.get('source_page')!=19
                or (evidence.get('year'),evidence.get('quarter'))!=(2026,3)
                or evidence.get('scope')!='group' or evidence.get('currency')!='DKK'
                or evidence.get('metrics')!=EXPECTED
                or alm.get('metrics',{}).get('solvency_ratio')!=238.0):
                errors.append('Alm. Brand presentation solvency evidence incomplete')
        if alm.get('source_type') != 'official_issuer_interim_announcement':
            errors.append('Alm. Brand source type must not claim PDF verification')
        if not str(alm.get('source_url', '')).startswith('https://investorrelations.almbrand.dk/'):
            errors.append('Alm. Brand official source URL missing')
        if alm.get('year') != 2026 or alm.get('quarter') != 3:
            errors.append('Alm. Brand verified snapshot is not Q3 2026')
        metrics = alm.get('metrics', {})
        if not REQUIRED.issubset(metrics) or not set(metrics).issubset(REQUIRED|{'insurance_revenue_growth','solvency_ratio','return_on_equity','profit_before_tax'}) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in metrics.values()
        ) or ('insurance_revenue_growth' in metrics and abs(metrics['insurance_revenue_growth']-1.6)>0.001):
            errors.append('Alm. Brand verified metric set is incomplete or invalid')
        errors.extend(validate_supplemental(alm))
    klp = insurers.get('KLP Skadeforsikring', {})
    if klp.get('status') == 'awaiting_source_verified_metrics' and klp.get('metrics') == {}:
        pass
    elif klp.get('status') == 'verified_official_pdf_reconciled':
        periods=klp.get('periods',[])
        from import_klp_production import snapshot_from_rows
        try:
            snapshot_from_rows(periods)
            period_history_ok=len(periods)>=3
        except (KeyError,TypeError,ValueError):
            period_history_ok=False
        if not period_history_ok:
            errors.append('KLP must provide contiguous verified PDF quarter periods starting Q1 2026')
        else:
            for index,p in enumerate(periods):
                if p.get('source_type')=='official_annual_report' or p.get('quarter_calculation'):
                    from klp_annual_q4 import validate_derived
                    errors.extend(validate_derived(p,periods[index-1] if index>0 else None))
                    continue
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

                if (p.get('year',0),p.get('quarter',0))>(2026,3):
                    ytd=p.get('ytd_metrics',{})
                    required=REQUIRED|{'insurance_revenue_growth','solvency_ratio','profit_before_tax'}
                    if set(ytd)!=required or any(type(v) not in (float,int) or not math.isfinite(v) for v in ytd.values()) or ytd.get('solvency_ratio')!=metrics.get('solvency_ratio'):
                        errors.append('KLP rolling HIÅ metrics incomplete or inconsistent')
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
                if growth.get('previous_year')!=p.get('year',0)-1 or growth.get('source_sha256')!=p.get('source_sha256'):
                    errors.append('KLP income-growth evidence source mismatch Q'+str(p.get('quarter')))
                if abs(float(metrics.get('insurance_revenue_growth',-10000))-float(growth.get('quarter',{}).get('growth_percent',-20000)))>1e-6:
                    errors.append('KLP published income growth differs from source-backed quarter growth')

            if (klp.get('year'),klp.get('quarter'))!=(periods[-1].get('year'),periods[-1].get('quarter')) or klp.get('metrics')!=periods[-1]['metrics'] or any(klp.get(k)!=periods[-1].get(k) for k in ('source_url','source_sha256','source_type','source_pages','ytd_metrics','metric_methods','quarter_calculation','source_documents')):
                errors.append('KLP latest published quarter does not match last verified period')
    else:
        errors.append('KLP metrics require source verification before publication')
    from import_extended_ytd import validate_baseline
    for item in insurers.values():
        errors.extend(validate_baseline(item))
    return errors


def main():
    extended = json.loads((ROOT / 'data/extended_insurer_financials.json').read_text())
    sources = json.loads((ROOT / 'data/report_sources.json').read_text())
    calendar = json.loads((ROOT / 'data/calendar.json').read_text())
    errors = validate(extended, sources, calendar)
    print(json.dumps({'nine_issuer_registry_checked': True,
                      'nine_company_financial_parity_certified': False,
                      'klp_metrics_verified': extended.get('insurers',{}).get('KLP Skadeforsikring',{}).get('status')=='verified_official_pdf_reconciled',
                      'alm_brand_pdf_page_import_verified': False,
                      'errors': errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
