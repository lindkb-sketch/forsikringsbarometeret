#!/usr/bin/env python3
"""Import Q3 2024 Protector Norway revenue from 2025 official PDF comparisons.

Do not substitute group totals or the Q3 2024 gross written premium.
A single exact official Norway segment row must identify Q3 2025 and Q3 2024.
"""
import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'data/financial_observations.json'
SOURCE='https://storage.mfn.se/34613cd2-9b91-47d8-bae6-1c5274fa1298/interim-report-q3-2025-prot.pdf'

def parse_norway_revenue(pages,url,sha):
    matches=[]
    for number,text in pages:
        if not re.search(r'^Segment information\s*-\s*Q3\s*$',text,re.M):
            continue
        if not re.search(r'UK\s+Sweden\s+Norway\s+Denmark\s+France',text):
            continue
        headers=re.findall(r'Q3\s+2025\s+Q3\s+2024',text)
        if len(headers)!=5:
            raise ValueError('Protector Norway Q3 year columns ambiguous')
        rows=re.findall(r'^Insurance revenue\s+([^\n]+)',text,re.M)
        if len(rows)!=1:
            raise ValueError('Missing unique official Norway insurance revenue row')
        amounts=re.findall(r'(?<![\w])-?\d[\d,]*',rows[0])
        if len(amounts)<6:raise ValueError('Norway revenue columns missing')
        current,prior=int(amounts[4].replace(',','')),int(amounts[5].replace(',',''))
        if current<=0 or prior<=0 or current==prior:
            raise ValueError('Invalid Norway revenue comparison amounts')
        matches.append((number,current,prior))
    if len(matches)!=1:
        raise ValueError('Expected exactly one Q3 official Norway segment table')
    page,current,prior=matches[0]
    return [
        dict(company='Protector',year=year,quarter=3,scope='norway',
             source_scope='norway',period_type='quarter',
             metric='insurance_revenue',value=value,unit='MNOK',
             status='reported',source_type='official_quarterly_report',
             source_url=url,source_page=page,source_sha256=sha,
             source_document_period='Q3 2025',
             source_section='Segment information - Q3 / Norway',
             source_definition='Official Norway insurance revenue, '+ 
                 ('prior-year comparative column' if year==2024 else 'current-year column'))
        for year,value in ((2025,current),(2024,prior))
    ]

def download():
    request=urllib.request.Request(SOURCE,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
    with urllib.request.urlopen(request,timeout=50) as response:
        if response.geturl().split('/')[2]!='storage.mfn.se':
            raise ValueError('Untrusted PDF redirect')
        blob=response.read(20_000_001)
    if len(blob)>20_000_000 or not blob.startswith(b'%PDF-'):
        raise ValueError('Missing official Protector PDF')
    return blob

def run():
    blob=download()
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        pages=[(n+1,page.extract_text(layout=False) or '') for n,page in enumerate(pdf.pages)]
    rows=parse_norway_revenue(pages,SOURCE,hashlib.sha256(blob).hexdigest())
    data=json.loads(OUTPUT.read_text(encoding='utf-8'))
    # Segment is part of the identity: Private Norway and Commercial Norway
    # must NEVER overwrite each other when adding a Protector observation.
    identity=('company','scope','segment','year','quarter','period_type','metric')
    index={tuple(r.get(k) for k in identity):r for r in data['observations']}
    if len(index)!=len(data['observations']):
        raise ValueError('Duplicate financial observation identities before Protector backfill')
    for row in rows:
        key=tuple(row.get(k) for k in identity)
        existing=index.get(key)
        if existing and abs(existing['value']-row['value'])>0.001:
            raise ValueError('Protector Norway historical PDF disagrees with existing verified amount')
        if not existing:index[key]=row
    # Preserve all existing issuer segments and original source provenance.
    data['observations']=list(index.values())
    from audit_financials import audit
    if not audit(data)['ok']:raise ValueError('Protector Norway historic source audit rejected')
    from publish_geographic_workbooks import atomic_write
    atomic_write(OUTPUT,data)
    print('PROTECTOR_NORWAY_Q3_2024_VERIFIED',rows[1]['value'],'PDF_PAGE',rows[1]['source_page'])
if __name__=='__main__':run()
