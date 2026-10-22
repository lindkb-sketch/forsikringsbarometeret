#!/usr/bin/env python3
"""Require every audited published group-quarter observation to reach the site feed."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMPANIES={'Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'}

def key(row):
    return (row['company'],row['year'],row['quarter'],row.get('scope'),
            row.get('period_type'),row['metric'],row.get('segment',''))

def validate(source,feed):
    if not COMPANIES.issubset({r['company'] for r in source}):
        raise ValueError('Financial source missing one or more registered insurers')
    expected={key(r):r for r in source if r['company'] in COMPANIES
              and r.get('status','reported') in ('reported','calculated')
              and not (r.get('scope')=='norway' and r.get('period_type')!='quarter')}
    actual={key(r):r for r in feed if r['company'] in COMPANIES}
    missing=expected.keys()-actual.keys()
    if missing:raise ValueError('Audited observations absent from website feed: '+repr(sorted(missing)[:12]))
    changed=[k for k in expected.keys() & actual.keys() if expected[k]!=actual[k]]
    if changed:raise ValueError('Website feed changed audited observations: '+repr(sorted(changed)[:12]))
    if len(actual)!=sum(r['company'] in COMPANIES for r in feed):
        raise ValueError('Duplicate insurer observations in feed')
    return {company:sorted({(r['year'],r['quarter']) for r in feed
                            if r['company']==company and r.get('scope')=='group'
                            and r.get('period_type')=='quarter'}) for company in sorted(COMPANIES)}

def run():
    source=json.loads((ROOT/'data/financial_observations.json').read_text())['observations']
    feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())['observations']
    print('Seven-insurer verified website feed parity:',validate(source,feed))

if __name__=='__main__':run()
