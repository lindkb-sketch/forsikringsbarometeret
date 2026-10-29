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
RETURN_TYPES={'Fremtind':'Eika','Gjensidige':'ROE','Tryg':'ROOF',
              'Protector':'ROE','Storebrand':'Cash return on equity'}
RETURN_QUARTERS=((2025,3),(2025,4),(2026,1),(2026,2),(2026,3))

def build(root=ROOT):
    root=Path(root)
    observations=json.loads((root/'data/financial_observations.json').read_text())['observations']
    registry=json.loads((root/'data/report_sources.json').read_text())['sources']
    feed_path=root/'data/verified_financial_feed.json'
    feed=json.loads(feed_path.read_text())['observations'] if feed_path.exists() else []
    workflow_path=root/'.github/workflows/update.yml'
    workflow=workflow_path.read_text(encoding='utf-8') if workflow_path.exists() else ''
    pipeline_path=root/'scripts/run_pipeline.py'
    pipeline=pipeline_path.read_text(encoding='utf-8') if pipeline_path.exists() else ''
    required_steps=('scripts/run_pipeline.py','scripts/publication_provenance.py',
                    'scripts/verify_public_pages.py','actions/deploy-pages@v4')
    scheduled=('schedule:' in workflow and all(step in workflow for step in required_steps))
    feed_index={(r.get('company'),r.get('year'),r.get('quarter'),r.get('scope'),
                 r.get('period_type'),r.get('metric'),r.get('segment')):r for r in feed}
    importer_map={'Fremtind':'import_fremtind_holding.py',
                  'Gjensidige':'import_gjensidige_latest.py',
                  'Tryg':'import_tryg.py','Sampo':'sampo_publish.py',
                  'Frende':'import_frende_holding.py',
                  'Protector':'protector_publish.py',
                  'Storebrand':'storebrand_publish_q3.py'}
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

        latest=max(((r['year'],r['quarter']) for r in group),default=None)
        latest_rows=[r for r in group if (r['year'],r['quarter'])==latest] if latest else []
        official=[r for r in latest_rows if r.get('source_type')=='official_quarterly_report'
                  and str(r.get('source_url','')).startswith('https://')]
        published=bool(latest_rows) and all(
            feed_index.get((r.get('company'),r.get('year'),r.get('quarter'),
                            r.get('scope'),r.get('period_type'),r.get('metric'),
                            r.get('segment')))==r for r in latest_rows)
        checks={
            'scheduled_workflow':scheduled,
            'issuer_importer_in_pipeline':importer_map[company] in pipeline,
            'official_source_on_latest_quarter':bool(official),
            'validated_latest_quarter_metrics':bool(latest and f"{latest[0]}-Q{latest[1]}" in complete),
            'source_to_feed_parity':published,
            # Historical observations do not establish how they were discovered.
            'fresh_report_discovery_observed':False,
            'fresh_report_ingested_without_manual_intervention':False,
            'public_pages_parity_observed_in_same_scheduled_run':False,
        }
        missing=[name for name,passed in checks.items() if not passed]
        return_status=None
        if company in RETURN_TYPES:
            checks={}
            for year,quarter in RETURN_QUARTERS:
                matches=[r for r in group if r.get('year')==year
                         and r.get('quarter')==quarter
                         and r.get('metric')=='return_on_equity'
                         and r.get('status')=='reported'
                         and r.get('source_type')=='official_quarterly_report'
                         and str(r.get('source_url','')).startswith('https://')
                         and isinstance(r.get('source_page'),int)
                         and r['source_page']>0
                         and RETURN_TYPES[company].lower() in
                             str(r.get('source_definition','')).lower()]
                checks[f'Q{quarter} {year}']=len(matches)==1
            return_status={'historical_source_verified':all(checks.values()),
                           'quarters':checks,
                           'scheduled_import_configured':True,
                           'future_quarter_end_to_end_verified':False}
        result.append({'company':company,'official_archive_registered':any(s.get('index_url') for s in sources),
          'direct_pdf_registered':sum(bool(s.get('document_url')) for s in sources),
          'official_report_candidates':sum(c.get('company')==company for c in candidate_rows),
          'candidate_discovery_verified':bool(candidate_data.get('complete')) if company in ('Frende','Fremtind') else False,
          'group_quarter_observations':len(group),'group_quarters_with_required_metrics':sorted(complete),
          'prior_year_growth_quarter':historical_growth_status('quarter'),
          'prior_year_growth_ytd':historical_growth_status('ytd'),
          'return_kpi_coverage':return_status,
          'e2e_evidence':checks,'missing_e2e_evidence':missing,
          'automatic_complete':not missing,
          'reason':'Verified across all required steps' if not missing else
                   'Missing end-to-end evidence: '+', '.join(missing)})
    return {'all_seven_automatic':all(x['automatic_complete'] for x in result),'companies':result,
       'return_kpi_history_complete':all(x['return_kpi_coverage']['historical_source_verified']
             for x in result if x['return_kpi_coverage'] is not None),
       'definition':'Automatic requires issuer discovery, fresh unattended import, official parsing, audited feed parity and public Pages parity in the same scheduled run; static repository evidence is insufficient.'}

if __name__=='__main__':
    output=ROOT/'data/report_coverage.json'
    output.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
    print('Coverage written:',output)
