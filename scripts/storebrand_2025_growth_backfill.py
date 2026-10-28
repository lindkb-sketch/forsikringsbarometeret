#!/usr/bin/env python3
"""Backfill 2025 Q1/Q2 Storebrand group growth comparators from issuer Q3 PDF."""
import json
import tempfile
from pathlib import Path
from audit_financials import DATA, audit
from publish_geographic_workbooks import atomic_write
from storebrand_sources import discover
from storebrand_automation_check import download_pdf
from import_storebrand_reports import parse_group

def run():
    source=discover(year=2025)['reports']
    candidates=[r for r in source if r['scope']=='group' and r['quarter']==3]
    if len(candidates)!=1:
        raise ValueError('Expected exactly one official Storebrand ASA 2025 Q3 PDF')
    url=candidates[0]['document_url']
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'storebrand-q3-2025.pdf'
        download_pdf(url,path)
        parsed=parse_group(path,url,2025,3)
    wanted=[r for r in parsed if r['scope']=='group'
            and r['year']==2025 and r['quarter'] in (1,2)
            and r['period_type']=='quarter' and r['metric']=='insurance_revenue']
    if len(wanted)!=2 or {r['quarter'] for r in wanted}!={1,2}:
        raise ValueError('Storebrand 2025 Q1/Q2 reported PDF columns missing')
    data=json.loads(DATA.read_text())
    rows=data['observations']
    key=lambda r:(r['company'],r['year'],r['quarter'],r['scope'],r['period_type'],r['metric'])
    existing={key(r):r for r in rows}
    added=0
    for row in wanted:
        previous=existing.get(key(row))
        if previous:
            if previous['value']!=row['value']:
                raise ValueError('Conflicting Storebrand PDF revenue comparator: '+str(key(row)))
        else:
            rows.append(row)
            added+=1
    if not audit(data)['ok']:
        raise ValueError('Storebrand PDF backfill failed source audit')
    if added:
        atomic_write(DATA,data)
    print('STOREBRAND_2025_PDF_GROWTH_COMPARATORS',added,flush=True)

if __name__=='__main__':
    run()
