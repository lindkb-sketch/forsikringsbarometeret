#!/usr/bin/env python3
"""Rebuild Q2 2026 Gjensidige Norway YTD from the real official PDF in replay only.

Reads issuer tables using the production YTD parser, never copies golden values.
Does not run in production and never publishes a replay artifact.
"""
import hashlib,json
from pathlib import Path
from audit_financials import DATA,audit
from ingest_official_pdf import download,read_pdf
from migrate_gjensidige_ytd_pdf import PDF,LABELS,SEGMENTS,source_values
from publish_geographic_workbooks import atomic_write

def run():
    blob=download(PDF)
    if not blob.startswith(b'%PDF-'):
        raise ValueError('Official Gjensidige YTD document is not PDF')
    digest=hashlib.sha256(blob).hexdigest()
    values,pages=source_values(read_pdf(blob))
    data=json.loads(Path(DATA).read_text(encoding='utf-8'))
    revenues={segment:values[segment]['insurance_revenue'] for segment in SEGMENTS}
    total=sum(revenues.values())
    if total<=0:raise ValueError('Invalid Norway YTD revenue denominators')
    rows=[]
    for segment in SEGMENTS:
        for metric in LABELS:
            rows.append(dict(company='Gjensidige',year=2026,quarter=2,
                scope='reported_segment',segment=segment,period_type='ytd',
                metric=metric,value=values[segment][metric],
                unit='percent' if 'ratio' in metric else 'MNOK',
                status='reported',source_type='official_quarterly_report',
                source_url=PDF,source_page=pages[segment],source_sha256=digest,
                source_section='General Insurance '+segment,
                source_document_period='Q2 2026'))
    for metric in LABELS:
        if metric in ('insurance_revenue','insurance_service_result'):
            amount=sum(values[s][metric] for s in SEGMENTS)
            calculation='sum_official_norway_segments'
        else:
            amount=sum(values[s][metric]*revenues[s] for s in SEGMENTS)/total
            calculation='revenue_weighted_official_norway_segments'
        rows.append(dict(company='Gjensidige',year=2026,quarter=2,
            scope='norway',period_type='ytd',metric=metric,value=amount,
            unit='percent' if 'ratio' in metric else 'MNOK',
            status='calculated',calculation=calculation,
            source_type='official_quarterly_report',source_url=PDF,
            source_page=pages[SEGMENTS[0]],source_sha256=digest,
            source_section='General Insurance Private Norway + Commercial Norway',
            source_document_period='Q2 2026'))
    fields=('company','year','quarter','scope','period_type','metric','segment')
    index={tuple(r.get(k) for k in fields):r for r in data['observations']}
    added=0
    for row in rows:
        key=tuple(row.get(k) for k in fields)
        if key in index:
            if abs(index[key]['value']-row['value'])>0.15:
                raise ValueError('Existing Norway YTD value conflicts with official PDF')
        else:
            index[key]=row
            added+=1
    updated={**data,'observations':list(index.values())}
    if not audit(updated)['ok']:
        raise ValueError('Source-verified Norway YTD replay failed financial audit')
    if added:atomic_write(DATA,updated)
    print('GJENSIDIGE_OFFICIAL_PDF_YTD_REPLAY',added)

if __name__=='__main__':run()
