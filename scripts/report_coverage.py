#!/usr/bin/env python3
"""Machine-readable, fail-honest report ingestion coverage for all seven issuers.

A report URL or successful download is NOT equivalent to a parsed financial
observation. This diagnostic is safe to publish and does not change numbers.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMPANIES=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')
REQUIRED=('insurance_revenue','insurance_service_result','combined_ratio')

def build(root=ROOT):
    root=Path(root)
    observations=json.loads((root/'data/financial_observations.json').read_text())['observations']
    registry=json.loads((root/'data/report_sources.json').read_text())['sources']
    result=[]
    candidate_path=root/'data/frende_fremtind_candidates.json'
    candidate_data=json.loads(candidate_path.read_text()) if candidate_path.exists() else {'candidates':[],'complete':False}
    candidate_rows=candidate_data.get('candidates',[]) if candidate_data.get('complete') else []
    for company in COMPANIES:
        sources=[s for s in registry if s['company']==company]
        group=[r for r in observations if r.get('company')==company and r.get('scope')=='group' and r.get('period_type')=='quarter']
        periods={f"{r['year']}-Q{r['quarter']}" for r in group}
        byperiod={p:{r['metric'] for r in group if f"{r['year']}-Q{r['quarter']}"==p} for p in periods}
        complete=[p for p,metrics in byperiod.items() if set(REQUIRED)<=metrics]
        # Last-year growth requires matching 2025/2024 source data, separately
        # for isolated quarter and cumulative YTD. Do not certify missing years.
        def historical_growth_status(kind):
            latest=max(((r['year'],r['quarter']) for r in observations
                        if r.get('company')==company and r.get('scope')=='group'
                        and r.get('period_type')==kind and r.get('metric')=='insurance_revenue'),
                       default=None)
            if latest is None:return {'available':False,'reason':'no verified revenue period'}
            year,quarter=latest
            def lookup(y,metric):
                return next((r for r in observations if r.get('company')==company
                             and r.get('scope')=='group' and r.get('period_type')==kind
                             and r.get('year')==y and r.get('quarter')==quarter
                             and r.get('metric')==metric
                             and r.get('status','reported') in ('reported','calculated')),None)
            reported=lookup(year-1,'insurance_revenue_growth')
            previous=lookup(year-1,'insurance_revenue')
            old=lookup(year-2,'insurance_revenue')
            available=bool(reported or previous and old and previous.get('unit')==old.get('unit') and old.get('value',0)>0)
            return {'available':available,'year':year-1,'quarter':quarter,
                    'reason':'reported growth' if reported else
                             'verified comparable revenue years' if available else
                             'missing verified revenue for prior-prior year'}

        result.append({'company':company,'official_archive_registered':any(s.get('index_url') for s in sources),
          'direct_pdf_registered':sum(bool(s.get('document_url')) for s in sources),
          'official_report_candidates':sum(c.get('company')==company for c in candidate_rows),
          'candidate_discovery_verified':bool(candidate_data.get('complete')) if company in ('Frende','Fremtind') else False,
          'group_quarter_observations':len(group),'group_quarters_with_required_metrics':sorted(complete),
          'prior_year_growth_quarter':historical_growth_status('quarter'),
          'prior_year_growth_ytd':historical_growth_status('ytd'),
          'automatic_complete':False,
          'reason':'End-to-end automatic discovery, source parsing and publication not yet verified for this issuer'})
    return {'all_seven_automatic':all(x['automatic_complete'] for x in result),'companies':result,
       'definition':'Automatic requires real official report discovery, extraction of validated numbers, and successful scheduled publication.'}

if __name__=='__main__':
    output=ROOT/'data/report_coverage.json'
    output.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
    print('Coverage written:',output)
