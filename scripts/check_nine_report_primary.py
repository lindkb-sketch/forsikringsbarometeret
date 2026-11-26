#!/usr/bin/env python3
"""Require original-report provenance for every displayed latest-quarter KPI."""
import json
import math
import re
from pathlib import Path
from check_nine_release import period
from quarterly_kpi_completeness import COMPANIES,METRICS,NOT_REPORTED
from build_nine_insurer_comparison import build
from check_extended_insurer_evidence import validate as validate_extended
from rolling_alm_brand_reports import validate_rolling

ROOT=Path(__file__).resolve().parents[1]

def report_row(row):
    if row.get('source_type') not in ('official_quarterly_report','official_annual_report'):return False
    if row.get('source_type')=='official_annual_report' and row.get('quarter')!=4:return False
    return (str(row.get('source_url','')).startswith('https://')
            and bool(re.fullmatch(r'[0-9a-f]{64}',str(row.get('source_sha256',''))))
            and type(row.get('source_page')) is int and row['source_page']>0
            and type(row.get('value')) in (int,float) and math.isfinite(row['value']))

def check(feed,extended,comparison):
    errors=[]
    if comparison!=build(feed,extended):
        errors.append('Comparison does not match the audited source projection')
    companies=comparison.get('companies',[])
    if len(companies)!=9 or {r.get('company') for r in companies}!=set(COMPANIES):
        return errors+['Nine distinct companies required']
    rows=feed.get('observations',[])
    for item in companies:
        c=item['company'];year,q=period(item['period'])
        if c in ('KLP Skadeforsikring','Alm. Brand'):
            original=extended.get('insurers',{}).get(c,{})
            if original.get('status')!='verified_official_pdf_reconciled':
                errors.append(c+': original report must be the primary source')
            if original.get('source_type') not in ('official_quarterly_report','official_annual_report'):
                errors.append(c+': non-report primary source')
            if item.get('source_url')!=original.get('source_url') or not re.fullmatch(r'[0-9a-f]{64}',str(original.get('source_sha256',''))):
                errors.append(c+': report link/fingerprint missing')
            if c=='Alm. Brand':errors.extend(validate_rolling(original))
            continue
        current=[r for r in rows if r.get('company')==c and r.get('scope')=='group'
                 and (r.get('year'),r.get('quarter'))==(year,q)
                 and r.get('metric') in METRICS and r.get('status') in ('reported','calculated')]
        for view,basis in [('metrics','quarter'),('ytd_metrics','ytd')]:
            for metric in METRICS:
                value=item.get(view,{}).get(metric)
                if value is None and metric in NOT_REPORTED.get(c,set()):continue
                if value is None:
                    errors.append(c+': missing '+view+':'+metric);continue
                actual=item.get('metric_periods',{}).get(metric,basis) if basis=='quarter' else basis
                matching=[r for r in current if r.get('metric')==metric and r.get('period_type')==actual]
                # Solvency is measured at the balance-sheet date, never summed.
                if metric=='solvency_ratio' and basis=='ytd' and not matching:
                    matching=[r for r in current if r.get('metric')==metric and r.get('period_type')=='quarter' and r.get('value')==value]
                if metric=='insurance_revenue_growth' and not matching:
                    # Projection computes growth only from same-scope, same
                    # basis current and prior-year revenues, not estimates.
                    matching=[r for r in current if r.get('metric')=='insurance_revenue' and r.get('period_type')==actual]
                    prior=[r for r in rows if r.get('company')==c and r.get('scope')=='group'
                           and (r.get('year'),r.get('quarter'))==(year-1,q)
                           and r.get('metric')=='insurance_revenue' and r.get('period_type')==actual
                           and r.get('status') in ('reported','calculated')]
                    if len(prior)!=1 or not report_row(prior[0]):
                        errors.append(c+': missing original prior-year revenue source')
                if len(matching)!=1 or not report_row(matching[0]):
                    errors.append(c+': unverified original report row '+view+':'+metric)
    return errors

def main():
    load=lambda name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
    feed,extended,comparison=map(load,('verified_financial_feed.json','extended_insurer_financials.json','nine_insurer_comparison.json'))
    errors=validate_extended(extended,load('report_sources.json'),load('calendar.json'))+check(feed,extended,comparison)
    print(json.dumps({'nine_company_report_primary':not errors,'errors':errors},ensure_ascii=False),flush=True)
    if errors:raise SystemExit('Nine-company original report provenance gate failed')

if __name__=='__main__':main()
