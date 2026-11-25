#!/usr/bin/env python3
"""Auditable nine-insurer KPI completeness inventory; never invent missing values."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = (
    'insurance_revenue', 'insurance_service_result', 'combined_ratio',
    'loss_ratio', 'expense_ratio', 'insurance_revenue_growth',
    'return_on_equity', 'solvency_ratio', 'profit_before_tax',
)
COMPANIES = (
    'Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende',
    'Protector', 'Storebrand', 'KLP Skadeforsikring', 'Alm. Brand',
)

# Reporting exceptions supplied by project owner; revisit if disclosure changes.
NOT_REPORTED = {'KLP Skadeforsikring': {'return_on_equity'},
                'Frende': {'return_on_equity', 'solvency_ratio'}}

def build(comparison,*,_ytd_only=False):
    rows = comparison.get('companies', [])
    by_company = {row['company']: row for row in rows}
    if len(rows) != len(COMPANIES) or set(by_company) != set(COMPANIES):
        raise ValueError('Nine-company comparison must contain exactly nine distinct issuers')
    result = []
    for company in COMPANIES:
        row = by_company[company]
        values = row.get('ytd_metrics' if _ytd_only else 'metrics') or {}
        exempt = [metric for metric in METRICS if metric in NOT_REPORTED.get(company, set()) and values.get(metric) is None]
        missing = [metric for metric in METRICS if values.get(metric) is None and metric not in exempt]
        unexpected = sorted(set(values) - set(METRICS))
        if unexpected:
            raise ValueError(f'{company}: unknown metrics: {unexpected}')
        observed = [metric for metric in METRICS if values.get(metric) is not None]
        result.append({
            'company': company, 'period': row.get('period'),
            'source_url': row.get('source_url'),
            'source_status': row.get('status'),
            'present_metrics': observed,
            'missing_metrics': missing,
            'not_reported_metrics': exempt,
            'reporting_exception_basis': 'project_owner_disclosure_policy' if exempt else None,
            'present_count': len(observed),
            'expected_count': len(METRICS) - len(exempt),
            'all_metrics_present': not missing,
            # A non-null value does NOT prove unattended import or dual-document provenance.
            'unattended_extraction_verified': False,
            'missing_reason': 'not_verified_in_comparison_feed' if missing else None,
        })
    periods = sorted({r['period'] for r in result if r['period']}, key=lambda p:(p.split()[-1],p.split()[0]))
    common_period = periods[0] if len(periods)==1 and all(r['period']==periods[0] for r in result) else None
    report = {
        'schema_version': 1,
        'all_nine_same_period': common_period is not None,
        'common_period': common_period,
        'reported_periods': periods,
        'purpose': 'non_destructive_latest_quarter_kpi_gap_inventory',
        'all_nine_metrics_present': all(r['all_metrics_present'] for r in result),
        'all_nine_unattended_extraction_verified': False,
        'expected_metric_count': sum(row['expected_count'] for row in result),
        'present_metric_count': sum(row['present_count'] for row in result),
        'missing_metric_count': sum(len(row['missing_metrics']) for row in result),
        'reporting_exception_count': sum(len(row['not_reported_metrics']) for row in result),
        'note': ('Missing values must remain null until validated against issuer sources. '
                 'This inventory is not proof of PDF extraction, source comparison, '
                 'automated scheduled ingestion or investor readiness.'),
        'companies': result,
    }
    if not _ytd_only:
        report['ytd']=build(comparison,_ytd_only=True)
        ytd_only=[{'company':r['company'],'metric':k} for r in rows for k,v in r.get('metric_periods',{}).items() if v=='ytd' and r.get('metrics',{}).get(k) is not None]
        report['isolated_quarter_metric_count']=report['present_metric_count']-len(ytd_only)
        report['ytd_only_return_metrics']=ytd_only
    else:
        report['purpose']='non_destructive_latest_ytd_kpi_gap_inventory'
    return report

def main():
    comparison = json.loads((ROOT / 'data/nine_insurer_comparison.json').read_text(encoding='utf-8'))
    report = build(comparison)
    target = ROOT / 'data/quarterly_kpi_completeness.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Quarterly KPI completeness:', json.dumps({
        'all_nine_metrics_present': report['all_nine_metrics_present'],
        'missing_by_company': {r['company']: r['missing_metrics'] for r in report['companies'] if r['missing_metrics']}
    }, ensure_ascii=False))
    print('YTD KPI completeness:',json.dumps({'present':report['ytd']['present_metric_count'],'expected':report['ytd']['expected_metric_count'],'missing_by_company':{r['company']:r['missing_metrics'] for r in report['ytd']['companies'] if r['missing_metrics']}},ensure_ascii=False))
    print('Saved', target)

if __name__ == '__main__':
    main()
