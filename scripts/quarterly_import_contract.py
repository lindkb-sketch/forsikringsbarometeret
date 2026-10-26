#!/usr/bin/env python3
"""Uniform seven-issuer post-import contract: source-validated, no invented quarters.

Run after every scheduled quarterly import, before deployment. It tests the
latest *actually imported* period per issuer rather than requiring a report
that the insurer has not yet released.
"""
import json
from pathlib import Path
from audit_financials import audit

ROOT=Path(__file__).resolve().parents[1]
COMPANIES=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')
BASE={'insurance_revenue','combined_ratio','loss_ratio','expense_ratio'}
RESULT_REQUIRED={'Fremtind','Gjensidige','Tryg','Sampo','Protector'}
AS_OF={'solvency_ratio'}
def key(r):
    return (r['company'],r['year'],r['quarter'],r['scope'],r['period_type'],r['metric'],r.get('segment'))

def verify(source,feed):
    result=audit({'observations':source})
    if not result['ok']:
        raise ValueError('Official-source audit failed: '+repr(result['errors'][:6]))
    index={key(r):r for r in feed}
    errors=[]
    report=[]
    for company in COMPANIES:
        rows=[r for r in source if r['company']==company and r['scope']=='group' and r['period_type']=='quarter'
              and r.get('status','reported') in ('reported','calculated')]
        dates=sorted({(r['year'],r['quarter']) for r in rows})
        if not dates:
            errors.append(company+': no previously verified quarterly group data')
            continue
        date=dates[-1]
        latest=[r for r in rows if (r['year'],r['quarter'])==date]
        metrics={r['metric'] for r in latest}
        required=BASE|({'insurance_service_result'} if company in RESULT_REQUIRED else set())
        missing=sorted(required-metrics)
        if missing:
            errors.append(f'{company} Q{date[1]} {date[0]}: imported report missing {missing}')
        for r in latest:
            matching=index.get(key(r))
            if matching!=r:
                errors.append(f'{company}: official observation missing/modified in published feed: {key(r)}')
        revenue=next((r for r in latest if r['metric']=='insurance_revenue'),None)
        if company=='Frende' and (not revenue or 'Sum driftsinntekter' not in revenue.get('source_definition','')):
            errors.append('Frende: revenue must be the reported Sum driftsinntekter, not IFRS insurance revenue')
        # Solvency is a balance-sheet snapshot, not a summable quarterly flow.
        for r in latest:
            if r['metric'] in AS_OF:
                other=next((x for x in source if x['company']==company and
                    x['year']==r['year'] and x['quarter']==r['quarter'] and
                    x['scope']=='group' and x['period_type']=='ytd' and x['metric']==r['metric']),None)
                if other and other['value']!=r['value']:
                    errors.append(f'{company}: quarter/YTD solvency differs at Q{date[1]} {date[0]}')
        report.append({'company':company,'latest_imported':f'Q{date[1]} {date[0]}',
                       'required_metrics_verified':not missing,
                       'missing':missing,'revenues_definition':revenue.get('source_definition') if revenue else None})
    if errors:
        raise ValueError('Quarterly automatic-import contract failed: '+'; '.join(errors))
    return report

def main():
    source=json.loads((ROOT/'data/financial_observations.json').read_text())['observations']
    feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())['observations']
    for item in verify(source,feed):
        print('VERIFIED_LATEST_IMPORT',json.dumps(item,ensure_ascii=False))
    print('All seven issuer imports pass current released-quarter source and publication contract')

if __name__=='__main__':main()
