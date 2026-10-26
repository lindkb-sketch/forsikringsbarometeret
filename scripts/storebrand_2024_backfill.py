#!/usr/bin/env python3
"""Verify Storebrand Insurance APM Q3 2024 comparatives from official Q3 2025 supplement.

Never substitute Storebrand ASA group turnover or Storebrand Forsikring AS
standalone numbers for the published Storebrand ASA Insurance reporting segment.
"""
import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path
import pdfplumber
from audit_financials import DATA, audit
from publish_geographic_workbooks import atomic_write

SOURCE='https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa/2025/_/attachment/inline/da62402f-d597-4d26-afc6-ad0ca6ab8039%3A0f32ecf07056118e0a078d4f6cd3a1de100f16e6/2025-3q-supplementary-information.pdf'
DESCRIPTION='APM: Insurance segment premiums f.o.a.; not IFRS insurance revenue'
def parse_pages(pages):
    found=[]
    for page,text in pages:
        if 'Table 23' not in text or 'Insurance' not in text:
            continue
        for line in text.splitlines():
            m=re.match(r'^\s*Insurance premiums f\.o\.a\.\s+(.+?)\s*$',line)
            if not m:continue
            amounts=re.findall(r'(?<!\d)\d{1,3}(?:[ ,]\d{3})*(?!\d)',m.group(1))
            if len(amounts)==8:
                values=[int(v.replace(' ','').replace(',','')) for v in amounts]
                if values[0]==2475 and values[5]==7140:
                    found.append((page,values))
    if len(found)!=1:raise ValueError('Storebrand Insurance Q3 2025 / 2024 line not unambiguous')
    page,values=found[0]
    return page,{('quarter',2025):values[0],('quarter',2024):values[4],
                 ('ytd',2025):values[5],('ytd',2024):values[6]}

def run():
    req=urllib.request.Request(SOURCE,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
    with urllib.request.urlopen(req,timeout=35) as resp:
        if not resp.geturl().startswith('https://www.storebrand.com/'):
            raise ValueError('Unexpected Storebrand redirect')
        blob=resp.read(35_000_001)
    if len(blob)>35_000_000 or not blob.startswith(b'%PDF-'):raise ValueError('Invalid Storebrand PDF')
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages)>250:raise ValueError('Storebrand PDF too large')
        pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
    page,values=parse_pages(pages)
    baseline=json.loads(DATA.read_text(encoding='utf-8'))
    if not audit(baseline)['ok']:raise ValueError('Storebrand baseline audit failed')
    rows=baseline['observations']
    def previous(kind,year):
        return [r for r in rows if r.get('company')=='Storebrand'
                and r.get('scope')=='group' and r.get('year')==year
                and r.get('quarter')==3 and r.get('period_type')==kind
                and r.get('metric')=='insurance_revenue']
    for kind in ('quarter','ytd'):
        old=previous(kind,2025)
        if len(old)!=1 or old[0]['value']!=values[(kind,2025)] or old[0].get('unit')!='MNOK':
            raise ValueError('Storebrand 2025 baseline does not match issuer supplement')
    digest=hashlib.sha256(blob).hexdigest()
    inserted=0
    for kind in ('quarter','ytd'):
        value=values[(kind,2024)]
        existing=previous(kind,2024)
        if existing:
            if len(existing)!=1 or abs(existing[0]['value']-value)>0.001:
                raise ValueError('Existing Storebrand 2024 source conflicts with official report')
            continue
        rows.append({'company':'Storebrand','year':2024,'quarter':3,'scope':'group',
                     'period_type':kind,'metric':'insurance_revenue','value':value,
                     'unit':'MNOK','status':'reported','source_type':'official_quarterly_report',
                     'source_url':SOURCE,'source_page':page,'source_sha256':digest,
                     'source_entity':'Storebrand ASA Insurance reporting segment',
                     'source_document_period':'Q3 2025',
                     'source_definition':DESCRIPTION+' (2024 comparison column)'})
        inserted+=1
    if inserted:
        if not audit(baseline)['ok']:raise ValueError('Storebrand source audit failed')
        atomic_write(DATA,baseline)
    print(json.dumps({'company':'Storebrand','added':inserted,'2024_quarter':values[('quarter',2024)],
                     '2024_ytd':values[('ytd',2024)],'source_page':page}))
if __name__=='__main__':run()
