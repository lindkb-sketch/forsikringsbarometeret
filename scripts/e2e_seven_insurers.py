#!/usr/bin/env python3
"""End-to-end integrity audit of all seven insurers and the public dashboard.

Not an assertion that a newly published report is already ingested: missing
quarters are recorded as incomplete, rather than fabricated or silently passed.
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMPANIES=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')
REQUIRED={'insurance_revenue','combined_ratio','loss_ratio','expense_ratio'}
KEY=('company','year','quarter','scope','period_type','metric','segment')
BASE='https://lindkb-sketch.github.io/forsikringsbarometeret/'
OUT=ROOT/'data/e2e_seven_insurers.json'

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def key(row):
    return tuple(row.get(k) for k in KEY)

def remote(path):
    request=urllib.request.Request(BASE+path+'?e2e='+str(time.time_ns()),
        headers={'Cache-Control':'no-cache','User-Agent':'Forsikringsbarometeret-E2E/1.0'})
    with urllib.request.urlopen(request,timeout=30) as response:
        if response.status!=200:
            raise ValueError(f'{path}: HTTP {response.status}')
        blob=response.read(4_000_001)
        if len(blob)>4_000_000:raise ValueError(f'{path}: oversized response')
        return blob.decode('utf-8')

def current_report_candidates(holding, generic, year=2026, quarter=3):
    """Derive explicit Q3 report candidates; never infer from financial calendar."""
    found=[r for r in holding if r.get('year')==year and r.get('quarter')==quarter]
    for r in generic:
        context=(r.get('link_text','')+' '+r.get('document_url','')).lower()
        # Do not mistake Q1-Q3 (year-to-date) for a Q3-only filing unless
        # the source is an official interim report showing Q3 explicitly.
        if (str(year) in context and
            re.search(r'(?<![a-z0-9])q'+str(quarter)+r'(?![0-9])|'+str(quarter)+r'\.\s*kvartal',context)):
            found.append({'company':r.get('company'),'year':year,'quarter':quarter,
                          'document_url':r.get('document_url')})
    return found

def publication_state(company, now, calendar, candidates, year, quarter):
    """Use confirmed issuer-report discovery ahead of optional calendar dates.

    A calendar forecasts publication but is not proof the PDF is available.
    """
    known=any(r.get('company')==company and r.get('year')==year
              and r.get('quarter')==quarter for r in candidates)
    if known:
        return 'publication_due', 'official_issuer_quarter_candidate_discovered'
    aliases={'Sampo':'Sampo / If'}
    company_calendar=calendar.get(aliases.get(company,company),{})
    dates=[event.get('date') for event in company_calendar.get('events',[])
           if event.get('period')=='Q3 2026' and event.get('date')]
    if dates:
        planned=date.fromisoformat(min(dates))
        if now < planned:
            return 'awaiting_publication', 'scheduled_for_'+planned.isoformat()
        return 'publication_expected', 'calendar_date_reached_but_no_verified_report'
    return 'publication_unconfirmed', 'no_verified_release_date_or_document'

def audit(public=True):
    source=read_json(ROOT/'data/financial_observations.json')['observations']
    feed=read_json(ROOT/'data/verified_financial_feed.json')['observations']
    editorial=read_json(ROOT/'data/quarterly_editorial.json')
    html=(ROOT/'index.html').read_text(encoding='utf-8')
    available=sorted({(r['year'],r['quarter']) for r in feed if r.get('scope')=='group' and r.get('period_type')=='quarter' and r.get('status') in ('reported','calculated') and r.get('metric')=='insurance_revenue'})
    if not available:raise ValueError('No verified reporting quarters available')
    year,quarter=available[-1]
    current_period=f'Q{quarter} {year}'
    issues=[]
    expected={key(r):r for r in source
              if r.get('status') in ('reported','calculated')}
    received={key(r):r for r in feed}
    if len(received)!=len(feed):issues.append('Duplicate keys in local verified feed')
    for k,r in expected.items():
        if received.get(k)!=r:issues.append('Source/feed mismatch: '+str(k))
    for marker in ('verified-q3-dashboard-bridge','profitabilityVerified','crPodium()',
                   'quarterly_editorial.json'):
        if marker not in html:issues.append('Missing homepage integration: '+marker)
    if editorial.get('period')!=current_period:issues.append('Quarterly editorial does not match latest verified period '+current_period)
    calendar=read_json(ROOT/'data/calendar.json')
    candidates_file=ROOT/'data/frende_fremtind_candidates.json'
    holding_candidates=read_json(candidates_file).get('candidates',[]) if candidates_file.exists() else []
    generic_file=ROOT/'data/report_candidates.json'
    generic_candidates=read_json(generic_file).get('candidates',[]) if generic_file.exists() else []
    candidates=current_report_candidates(holding_candidates,generic_candidates,year,quarter)
    today=datetime.now(timezone.utc).date()
    groups=[]
    for company in COMPANIES:
        q3=[r for r in feed if r.get('company')==company and r.get('year')==year
             and r.get('quarter')==quarter and r.get('scope')=='group'
             and r.get('period_type')=='quarter' and r.get('status')=='reported']
        q3metrics={r['metric'] for r in q3}
        q3prior=[r for r in feed if r.get('company')==company and r.get('year')==year-1
                 and r.get('quarter')==quarter and r.get('scope')=='group'
                 and r.get('period_type')=='quarter' and r.get('status')=='reported']
        documented=[]
        for r in q3:
            if not r.get('source_url','').startswith('https://') or not r.get('source_page') or not r.get('source_sha256'):
                documented.append(r.get('metric'))
        missing=sorted(REQUIRED-q3metrics)
        release,release_evidence=publication_state(company,today,calendar,candidates,year,quarter)
        status=('ready' if not missing and not documented else
                'awaiting_publication' if release in ('awaiting_publication','publication_unconfirmed','publication_expected') else
                'missing_import_or_verification')
        groups.append({'company':company,'status':status,'publication_state':release,
                       'publication_evidence':release_evidence,'current_quarter_metrics':sorted(q3metrics),
                       'current_quarter_missing':missing,'prior_year_quarter_available_metrics':sorted({r['metric'] for r in q3prior}),
                       'current_quarter_missing_source_provenance':documented})
    if public:
        public_errors=[]
        for attempt in range(3):
            try:
                public_feed=json.loads(remote('data/verified_financial_feed.json'))
                public_html=remote('index.html')
                public_editorial=json.loads(remote('data/quarterly_editorial.json'))
                if public_feed['observations']!=feed:raise ValueError('Public JSON differs from main feed')
                if public_html!=html:raise ValueError('Public HTML differs from main')
                if public_editorial!=editorial:raise ValueError('Public editorial differs from main')
                public_errors=[]
                break
            except Exception as exc:
                public_errors=[str(exc)]
                if attempt!=2:time.sleep(10)
        issues.extend('Public deploy: '+x for x in public_errors)
    incomplete=[c['company'] for c in groups if c['status']=='missing_import_or_verification']
    awaiting=[c['company'] for c in groups if c['status']=='awaiting_publication']
    ready=[c['company'] for c in groups if c['status']=='ready']
    report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'period':current_period,'scope':'group','companies':groups,
            'ready_companies':len(ready),'eligible_companies':len(ready)+len(incomplete),
            'awaiting_publication':awaiting,'total_companies':len(groups),
            'incomplete_companies':incomplete,'integrity_errors':issues,
            'overall':'pass' if not incomplete and not issues else 'fail'}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for c in groups:
        print('E2E',c['company'],c['status'],'missing',','.join(c['current_quarter_missing']) or '-',
              'prior-year',len(c['prior_year_quarter_available_metrics']))
    print('E2E_RESULT',report['overall'],'ready',report['ready_companies'],'/',report['eligible_companies'],'eligible',
          'integrity_errors',len(issues),'report',str(OUT),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    try:
        result=audit(public=not args.offline)
    except Exception as exc:
        OUT.write_text(json.dumps({'overall':'fail','fatal_error':repr(exc)},indent=2)+'\n')
        raise
    sys.exit(0 if result['overall']=='pass' else 1)
