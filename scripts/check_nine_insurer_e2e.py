#!/usr/bin/env python3
"""Milestone 5: nine-insurer source-to-comparison E2E contract.

No fabricated investor approval: seven feed and two extended insurers have distinct
sources, and document-level dual verification remains a separate milestone-4 gate.
"""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SEVEN=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')
NINE=SEVEN+('KLP Skadeforsikring','Alm. Brand')
CORE=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio')
METRICS=CORE+('insurance_revenue_growth','return_on_equity','solvency_ratio','profit_before_tax')
VERIFIED=('reported','calculated')
EXTENDED=('verified_official_pdf_reconciled','verified_official_presentation_reconciled')

def finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def check(feed,extended,comparison,gaps):
    errors=[]
    rows=feed.get('observations',[])
    companies=comparison.get('companies',[])
    if comparison.get('count')!=9 or len(companies)!=9 or tuple(x.get('company') for x in companies)!=NINE:
        errors.append('comparison must contain nine companies in canonical order')
    if comparison.get('investor_use_approved') is not False:
        errors.append('investor approval cannot be inferred from a successful test')
    if gaps.get('all_seven_dual_document_verified') is not False:
        errors.append('dual-document audit may not falsely certify all seven')
    gap_companies={c.get('company'):c for c in gaps.get('companies',[])}
    if set(gap_companies)!=set(SEVEN):
        errors.append('seven-source gap inventory incomplete')
    for company in SEVEN:
        item=next((x for x in companies if x.get('company')==company),None)
        if not item:continue
        relevant=[x for x in rows if x.get('company')==company and
                  x.get('scope')=='group' and x.get('period_type')=='quarter' and
                  x.get('status') in VERIFIED]
        if not relevant:
            errors.append(company+': no verified group quarters')
            continue
        latest=max((x['year'],x['quarter']) for x in relevant)
        latest_rows=[x for x in relevant if (x['year'],x['quarter'])==latest]
        if item.get('period')!=f'Q{latest[1]} {latest[0]}':
            errors.append(company+': comparison period mismatch')
        if item.get('status')!='verified_quarterly_feed':
            errors.append(company+': unverified comparison status')
        for metric in CORE:
            candidates=[x for x in latest_rows if x.get('metric')==metric]
            if len(candidates)!=1:
                errors.append(company+': missing or duplicate '+metric)
                continue
            row=candidates[0]
            if not finite(row.get('value')) or item.get('metrics',{}).get(metric)!=row['value']:
                errors.append(company+': value mismatch '+metric)
            if not str(row.get('source_url','')).startswith('https://'):
                errors.append(company+': missing source URL '+metric)
            if not isinstance(row.get('source_page'),int) or row['source_page']<1:
                errors.append(company+': missing page '+metric)
            sha=row.get('source_sha256','')
            if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
                errors.append(company+': invalid source digest '+metric)
        for metric in METRICS:
            if metric in CORE or metric=='insurance_revenue_growth':continue
            matching=[x for x in latest_rows if x.get('metric')==metric]
            if len(matching)>1:
                errors.append(company+': duplicate optional metric '+metric)
            if len(matching)==1 and item.get('metrics',{}).get(metric)!=matching[0]['value']:
                errors.append(company+': optional value mismatch '+metric)
        if company == 'Sampo' and item.get('metric_periods',{}).get('return_on_equity') == 'ytd':
            matches=[x for x in rows if x.get('company')==company
                     and x.get('scope')=='group' and x.get('period_type')=='ytd'
                     and (x.get('year'),x.get('quarter'))==latest
                     and x.get('metric')=='return_on_equity' and x.get('status')=='reported'
                     and x.get('source_definition')=='Return on equity own funds (RoEOF; issuer definition)']
            evidence=item.get('metric_sources',{}).get('return_on_equity',{})
            if (len(matches)!=1 or not finite(matches[0].get('value'))
                or item.get('metrics',{}).get('return_on_equity')!=matches[0]['value']
                or evidence.get('period_type')!='ytd'
                or any(evidence.get(k)!=matches[0].get(k) for k in ('source_url','source_page','source_sha256','source_definition'))
                or not str(evidence.get('source_url','')).startswith('https://')
                or not isinstance(evidence.get('source_page'),int) or evidence['source_page']<1
                or len(str(evidence.get('source_sha256','')))!=64):
                errors.append(company+': unverified YTD RoEOF evidence')
        gap=gap_companies.get(company,{})
        if gap.get('both_documents_checked_for_this_period') is True and gap.get('quarter_presentation_sourced_observations',0)==0:
            errors.append(company+': unjustified both-documents-checked flag')
    for company in NINE[7:]:
        source=extended.get('insurers',{}).get(company)
        item=next((x for x in companies if x.get('company')==company),None)
        if not source or not item:
            errors.append(company+': missing extended source/comparison')
            continue
        if source.get('status') not in EXTENDED or item.get('status')!=source['status']:
            errors.append(company+': extended evidence status mismatch')
        if item.get('period')!=f"Q{source.get('quarter')} {source.get('year')}":
            errors.append(company+': extended period mismatch')
        if item.get('currency')!=source.get('currency'):
            errors.append(company+': currency mismatch')
        if item.get('source_url')!=source.get('source_url'):
            errors.append(company+': primary source URL mismatch')
        for metric in METRICS:
            if item.get('metrics',{}).get(metric)!=source.get('metrics',{}).get(metric):
                errors.append(company+': metric mismatch '+metric)
        if company=='Alm. Brand':
            if (source.get('year',0),source.get('quarter',0))>(2026,3):
                from rolling_alm_brand_reports import validate_rolling
                errors.extend(validate_rolling(source))
            else:
                from import_alm_brand_supplemental import validate_supplemental
                errors.extend(validate_supplemental(source))
                ev=source.get('presentation_evidence',{})
                if (source.get('metrics',{}).get('solvency_ratio')!=238
                    or ev.get('source_page')!=19
                    or ev.get('metrics',{}).get('solvency_ratio')!=238
                    or len(str(ev.get('source_sha256','')))!=64):
                    errors.append('Alm. Brand: Q3 presentation provenance mismatch')
        if company=='KLP Skadeforsikring':
            if source.get('metrics',{}).get('return_on_equity') is not None:
                errors.append('KLP: unverified ROE must remain absent')
            if len(source.get('periods',[]))<3:
                errors.append('KLP: historical PDF quarter reconciliations required')
            elif all(isinstance(p,dict) and p.get('year') for p in source['periods']):
                from import_klp_production import snapshot_from_rows
                try:
                    from klp_annual_q4 import validate_derived
                    for i,p in enumerate(source['periods']):
                        if p.get('source_type')=='official_annual_report' or p.get('quarter_calculation'):
                            errors.extend(validate_derived(p,source['periods'][i-1] if i>0 else None))
                    snapshot=snapshot_from_rows(source['periods'])
                    if (snapshot['year'],snapshot['quarter'],snapshot['metrics'])!=(source.get('year'),source.get('quarter'),source.get('metrics')):
                        raise ValueError('Latest snapshot mismatch')
                    if source.get('quarter_calculation') and item.get('metric_methods')!=source.get('metric_methods'):
                        errors.append('KLP derived Q4 metric methods missing from comparison')
                except (ValueError,KeyError,TypeError):
                    errors.append('KLP: invalid rolling PDF quarter history')
    return errors

def main():
    feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
    extended=json.loads((ROOT/'data/extended_insurer_financials.json').read_text())
    comparison=json.loads((ROOT/'data/nine_insurer_comparison.json').read_text())
    gaps=json.loads((ROOT/'data/seven_insurer_source_gap_audit.json').read_text())
    errors=check(feed,extended,comparison,gaps)
    print(json.dumps({'nine_insurer_e2e_contract_pass':not errors,
                      'dual_document_all_nine_certified':False,
                      'errors':errors},ensure_ascii=False))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
