#!/usr/bin/env python3
"""Nine-insurer comparison with explicit non-comparable and missing states."""
import json
from pathlib import Path
from prior_year_growth_coverage import basis as revenue_basis

ROOT = Path(__file__).resolve().parents[1]
COMPANIES = ('Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende',
             'Protector', 'Storebrand', 'KLP Skadeforsikring', 'Alm. Brand')
METRICS = ('insurance_revenue', 'insurance_service_result', 'combined_ratio',
           'loss_ratio', 'expense_ratio', 'insurance_revenue_growth',
           'return_on_equity', 'solvency_ratio', 'profit_before_tax')


def build(feed, extended):
    observations = feed.get('observations', [])
    ext = extended.get('insurers', {})
    result = []
    for company in COMPANIES:
        metric_periods = {}
        metric_sources = {}
        if company in ext:
            item = ext[company]
            values = item.get('metrics', {})
            state=item.get('status')
            verified=state in ('verified_issuer_announcement','verified_official_pdf_reconciled','verified_official_presentation_reconciled')
            period = f"Q{item['quarter']} {item['year']}" if verified else None
            source = item.get('source_url') if verified else None
            status = ('verified_official_pdf_reconciled' if state=='verified_official_pdf_reconciled'
                      else 'verified_official_presentation_reconciled' if state=='verified_official_presentation_reconciled'
                      else 'issuer_announcement_only' if state=='verified_issuer_announcement'
                      else 'unverified_missing')
            currency = item.get('currency') if verified else None
        else:
            rows = [r for r in observations if r.get('company') == company
                    and r.get('scope') == 'group'
                    and r.get('period_type') == 'quarter'
                    and r.get('status') in ('reported', 'calculated')]
            periods = sorted({(r['year'], r['quarter']) for r in rows})
            latest = periods[-1] if periods else None
            current = [r for r in rows if (r['year'], r['quarter']) == latest] if latest else []
            values = {r['metric']: r['value'] for r in current if r.get('metric') in METRICS}
            if company == 'Sampo' and latest:
                # A source-labelled YTD RoEOF is not an isolated-quarter ROE.
                ytd = [r for r in observations if r.get('company') == company
                       and r.get('scope') == 'group' and r.get('period_type') == 'ytd'
                       and (r.get('year'), r.get('quarter')) == latest
                       and r.get('metric') == 'return_on_equity'
                       and r.get('status') == 'reported'
                       and r.get('source_definition') == 'Return on equity own funds (RoEOF; issuer definition)']
                if 'return_on_equity' not in values and len(ytd) == 1:
                    values['return_on_equity'] = ytd[0]['value']
                    metric_periods['return_on_equity'] = 'ytd'
                    current = current + ytd
                for row in current:
                    if row.get('metric') in ('return_on_equity','profit_before_tax','solvency_ratio'):
                        metric_sources[row['metric']] = {k:row.get(k) for k in ('source_url','source_page','source_sha256','source_definition','period_type')}
            # Match current isolated quarter with the same quarter one year
            # earlier, on the same company, scope, unit and revenue definition.
            if latest and 'insurance_revenue_growth' not in values:
                curr = next((r for r in current if r.get('metric')=='insurance_revenue'
                             and r.get('source_url')),None)
                prior = [r for r in observations if r.get('company')==company
                         and r.get('scope')=='group' and r.get('period_type')=='quarter'
                         and r.get('year')==latest[0]-1 and r.get('quarter')==latest[1]
                         and r.get('metric')=='insurance_revenue'
                         and r.get('status') in ('reported','calculated')
                         and r.get('source_url')]
                if curr and len(prior)==1 and isinstance(prior[0].get('value'),(float,int)) and prior[0]['value']>0 and curr.get('unit')==prior[0].get('unit') and revenue_basis(curr)==revenue_basis(prior[0]):
                    values['insurance_revenue_growth']=(curr['value']/prior[0]['value']-1)*100

            period = f'Q{latest[1]} {latest[0]}' if latest else None
            source = next((r.get('source_url') for r in current if r.get('source_url')), None)
            status = 'verified_quarterly_feed' if latest else 'unverified_missing'
            currency = next((r.get('currency') for r in current if r.get('currency')), None)
        result.append({
            'company': company, 'period': period, 'currency': currency,
            'status': status, 'source_url': source,
            'metrics': {key: values.get(key) if status != 'unverified_missing' else None for key in METRICS},
            **({'metric_periods': metric_periods, 'metric_sources': metric_sources} if metric_periods or metric_sources else {}),
            'revenue_comparable': company not in ('Frende', 'Storebrand', 'KLP Skadeforsikring') and status != 'unverified_missing',
        })
    return {'schema_version': 1, 'count': len(result),
            'investor_use_approved': False,
            'note': 'Growth is period-matched insurance revenue versus previous year; ROE/ROOF and solvency are issuer-specific; investment return is not a substitute; do not aggregate currencies or unlike accounting scopes. Missing values are null.',
            'companies': result}


def main():
    feed = json.loads((ROOT / 'data/verified_financial_feed.json').read_text())
    extended = json.loads((ROOT / 'data/extended_insurer_financials.json').read_text())
    output = build(feed, extended)
    target = ROOT / 'data/nine_insurer_comparison.json'
    serialized = json.dumps(output, ensure_ascii=False, indent=2) + '\n'
    if not target.exists() or target.read_text() != serialized:
        target.write_text(serialized)
    print('Nine-insurer comparison generated; investor_use_approved=false')


if __name__ == '__main__':
    main()
