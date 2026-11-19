#!/usr/bin/env python3
"""Non-destructive seven-insurer Q3 source inventory, not dual-document certification.

Never infer that absence of a discovered presentation means the issuer published none.
Candidate links are unverified and may refer to other reporting periods.
"""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMPANIES=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')
METRICS=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio',
         'expense_ratio','insurance_revenue_growth','return_on_equity','solvency_ratio',
         'profit_before_tax')
REQUIRED=METRICS[:5]

def audit(feed,candidates,coverage,year=2026,quarter=3):
    rows=feed.get('observations',[])
    links=candidates.get('candidates',[])
    out=[]
    for company in COMPANIES:
        selected=[r for r in rows if r.get('company')==company
                  and (r.get('year'),r.get('quarter'))==(year,quarter)
                  and r.get('scope')=='group' and r.get('period_type')=='quarter'
                  and r.get('status') in ('reported','calculated')]
        by_metric={}
        for r in selected:
            by_metric.setdefault(r.get('metric'),[]).append(r)
        present=sorted(k for k in METRICS if k in by_metric)
        provenance_errors=[]
        for metric,observations in by_metric.items():
            if metric not in METRICS:continue
            if len(observations)!=1:
                provenance_errors.append('ambiguous_duplicate:'+metric)
            for r in observations:
                if not str(r.get('source_url','')).startswith('https://'):
                    provenance_errors.append('missing_https_source:'+metric)
                if not isinstance(r.get('source_page'),int) or r['source_page']<1:
                    provenance_errors.append('missing_source_page:'+metric)
                sha=r.get('source_sha256','')
                if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
                    provenance_errors.append('missing_pdf_sha256:'+metric)
                if r.get('source_type') not in ('official_quarterly_report','official_results_presentation'):
                    provenance_errors.append('unknown_source_type:'+metric)
        found=[r for r in links if r.get('company')==company]
        types=Counter(r.get('document_type') for r in found)
        presentation_observations=sum(r.get('source_type')=='official_results_presentation'
                                      for r in selected)
        report_observations=sum(r.get('source_type')=='official_quarterly_report'
                                for r in selected)
        out.append({
            'company':company,'period':f'Q{quarter} {year}',
            'required_metrics_present':all(k in by_metric for k in REQUIRED),
            'verified_metrics':present,
            'not_present_in_quarter_feed':[k for k in METRICS if k not in by_metric],
            'quarter_report_sourced_observations':report_observations,
            'quarter_presentation_sourced_observations':presentation_observations,
            'unverified_report_candidates_all_periods':types['quarterly_report'],
            'unverified_presentation_candidates_all_periods':types['results_presentation'],
            'provenance_errors':sorted(set(provenance_errors)),
            'both_documents_checked_for_this_period':False,
            'presentation_metric_gap_status':'not_audited_against_official_presentation',
        })
    return {'schema_version':1,'purpose':'non_destructive_seven_insurer_source_gap_inventory',
            'period':f'Q{quarter} {year}',
            'all_seven_quarter_core_metrics_present':all(x['required_metrics_present'] for x in out),
            'all_seven_dual_document_verified':False,
            'discovery_complete':candidates.get('complete',False),
            'discovery_errors':candidates.get('errors',[]),
            'note':'Candidate counts cover all periods and do not prove period-specific presentation coverage. Report provenance is carried from the existing verified feed, not independently re-downloaded here. Never mark a metric missing until both documents are checked.',
            'companies':out}

def main():
    feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
    candidates=json.loads((ROOT/'data/report_candidates.json').read_text())
    coverage=json.loads((ROOT/'data/report_coverage.json').read_text())
    result=audit(feed,candidates,coverage)
    target=ROOT/'data/seven_insurer_source_gap_audit.json'
    serialized=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if not target.exists() or target.read_text()!=serialized:
        target.write_text(serialized)
    print('SEVEN_INSURER_Q3_SOURCE_AUDIT',json.dumps({
        'core_metrics_present':result['all_seven_quarter_core_metrics_present'],
        'dual_document_verified':result['all_seven_dual_document_verified'],
        'presentation_sourced':{r['company']:r['quarter_presentation_sourced_observations'] for r in result['companies']},
        'provenance_errors':{r['company']:r['provenance_errors'] for r in result['companies'] if r['provenance_errors']}
    },ensure_ascii=False))

if __name__=='__main__':main()
