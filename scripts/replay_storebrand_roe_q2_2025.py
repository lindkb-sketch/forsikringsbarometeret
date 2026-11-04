#!/usr/bin/env python3
"""Replay Storebrand Q2 2025 cash ROE from its labelled column in 2026 Q2 PDF.

Historical replay only. Never populate a missing return from a nearest number,
an unlabelled table, or a golden reference value.
"""
import json
import re
import tempfile
from pathlib import Path

from audit_financials import DATA, audit, ROOT
from import_storebrand_reports import pages, _unique_table, row, english
from publish_geographic_workbooks import atomic_write
from storebrand_automation_check import download_pdf

FIELDS=('company','year','quarter','scope','period_type','metric','segment')


def parse_roe(texts):
    page,table=_unique_table(texts,'Group - Key figures')
    section=table.split('Group - Key figures',1)[1].split('Financial metrics',1)[0]
    lines=[' '.join(line.split()) for line in section.splitlines()]
    header='Q2 Q1 Q4 Q3 Q2 2026 2025 2025'
    if lines.count(header)!=1:
        raise ValueError('Storebrand official historical ROE quarter header missing/ambiguous')
    if not any(re.fullmatch(r'2026 2025 01\.01\s*-\s*30\.06 Full year',x) for x in lines):
        raise ValueError('Storebrand ROE year and YTD header missing')
    values=row(section,'Cash return on equity, annualised (%)',8,english)
    if len(values)!=8:
        raise ValueError('Storebrand group ROE table column count changed')
    # Explicit header: 2026 Q2,Q1; 2025 Q4,Q3,Q2; 2026 H1; 2025 H1,FY.
    q4_2025,q2_2025=values[2],values[4]
    if not (-100<q2_2025<200):
        raise ValueError('Implausible Storebrand annualised ROE')
    return page+1,q2_2025,q4_2025


def run():
    golden=json.loads((ROOT/'data/golden_observations.json').read_text())['observations']
    matches=[r for r in golden if r.get('company')=='Storebrand'
             and r.get('year')==2025 and r.get('quarter')==2
             and r.get('scope')=='group' and r.get('period_type')=='quarter'
             and r.get('metric')=='return_on_equity'
             and r.get('source_type')=='official_quarterly_report']
    if len(matches)!=1:raise ValueError('Unique original Storebrand Q2 2025 ROE evidence required')
    reference=matches[0]
    url=reference['source_url']
    if not url.startswith('https://www.storebrand.com/'):
        raise ValueError('Unexpected Storebrand original issuer URL')
    with tempfile.TemporaryDirectory(prefix='storebrand-roe-replay-') as d:
        path=Path(d)/'source.pdf'
        download_pdf(url,path)
        texts,digest=pages(path,'Storebrand Group',2026)
    if digest!=reference.get('source_sha256'):
        raise ValueError('Original Storebrand PDF SHA-256 mismatch')
    page,value,q4=parse_roe(texts)
    if page!=reference.get('source_page') or abs(value-reference['value'])>0.01:
        raise ValueError('Storebrand Q2 2025 ROE independent reparse conflicts with original evidence')
    data=json.loads(DATA.read_text())
    index={tuple(r.get(k) for k in FIELDS):r for r in data['observations']}
    q4key=('Storebrand',2025,4,'group','quarter','return_on_equity',None)
    if q4key in index and abs(index[q4key]['value']-q4)>0.01:
        raise ValueError('Storebrand 2025 Q4 ROE column disagrees with independently imported Q4')
    key=('Storebrand',2025,2,'group','quarter','return_on_equity',None)
    if key not in index:
        index[key]=dict(company='Storebrand',year=2025,quarter=2,scope='group',
            source_scope='group',period_type='quarter',metric='return_on_equity',
            value=value,unit='percent',status='reported',
            source_type='official_quarterly_report',source_url=url,
            source_page=page,source_sha256=digest,
            source_document_period='Q2 2026',
            source_definition='Cash return on equity, annualised (%); explicitly labelled Q2 2025 column of Storebrand ASA Q2 2026 Group key figures')
        merged={**data,'observations':list(index.values())}
        if not audit(merged)['ok']:raise ValueError('Storebrand source-verified ROE replay failed audit')
        atomic_write(DATA,merged)
    print('STOREBRAND_Q2_2025_ROE_REPLAY_VERIFIED',value,'PDF_PAGE',page,'Q4_2025_COMPARATOR',q4)


if __name__=='__main__':run()
