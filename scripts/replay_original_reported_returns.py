#!/usr/bin/env python3
"""Replay historical published equity returns from original fingerprinted issuer PDFs.

Uses golden observations solely as a registry of original source URLs, SHA-256,
page and an equality oracle. The numeric value must be parsed again from source.
Only used in disposable historical replay, never in scheduled production.
"""
import argparse
import hashlib
import json
from pathlib import Path

from audit_financials import DATA, audit
from import_reported_returns import LABELS, extract
from ingest_official_pdf import download
from publish_geographic_workbooks import atomic_write

ROOT=Path(__file__).resolve().parents[1]
FIELDS=('company','year','quarter','scope','period_type','metric','segment')

def reconstruct(data,golden,company,fetch=download,parser=extract):
    if company not in LABELS:
        raise ValueError('Unsupported reported-return issuer')
    existing={tuple(row.get(k) for k in FIELDS):row for row in data['observations']}
    targets=[r for r in golden if r.get('company')==company
             and r.get('scope')=='group' and r.get('metric')=='return_on_equity'
             and r.get('status')=='reported' and r.get('year',0)>=2025
             and r.get('source_type')=='official_quarterly_report'
             and tuple(r.get(k) for k in FIELDS) not in existing]
    downloads={}
    added=[]; blocked=[]
    for target in targets:
        year,quarter=target['year'],target['quarter']
        period=target.get('period_type')
        url=target.get('source_url','')
        if not url.startswith('https://') or not target.get('source_page') or not target.get('source_sha256'):
            blocked.append((year,quarter,period,'missing original source provenance'));continue
        try:
            if url not in downloads:
                downloads[url]=fetch(url)
            blob=downloads[url]
            if not blob.startswith(b'%PDF-') or hashlib.sha256(blob).hexdigest()!=target['source_sha256']:
                raise ValueError('Original source PDF fingerprint mismatch')
            page,value,definition=parser(blob,company,year,quarter)
            if page!=target['source_page']:
                raise ValueError('Official return table page differs from verified source')
            if abs(value-target['value'])>0.01:
                raise ValueError('Re-parsed return conflicts with verified original value')
            if period=='ytd' and quarter!=1:
                raise ValueError('YTD return needs independent period-specific extraction')
            if period not in ('quarter','ytd'):
                raise ValueError('Unsupported return period')
            row=dict(company=company,year=year,quarter=quarter,scope='group',
                source_scope='group',period_type=period,metric='return_on_equity',
                value=value,unit='percent',status='reported',
                source_type='official_quarterly_report',source_url=url,
                source_page=page,source_sha256=hashlib.sha256(blob).hexdigest(),
                source_document_period=target.get('source_document_period',f'Q{quarter} {year}'),
                source_definition=definition+'; original verified source replay')
            existing[tuple(row.get(k) for k in FIELDS)]=row
            added.append((year,quarter,period,value))
        except (ValueError,OSError,TimeoutError) as exc:
            blocked.append((year,quarter,period,type(exc).__name__+': '+str(exc)[:180]))
    result={**data,'observations':list(existing.values())}
    if not audit(result)['ok']:
        raise ValueError('Historical reported-return replay failed source audit')
    return result,added,blocked

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--company',required=True,choices=sorted(LABELS))
    args=parser.parse_args()
    golden=json.loads((ROOT/'data/golden_observations.json').read_text())['observations']
    original=json.loads(DATA.read_text())
    updated,added,blocked=reconstruct(original,golden,args.company)
    if added:atomic_write(DATA,updated)
    print(json.dumps({'company':args.company,'restored':added,'unresolved':blocked,
                      'method':'reparsed_original_sha256_verified_pdf_not_copied_golden_values'},
                     ensure_ascii=False))
if __name__=='__main__':main()
