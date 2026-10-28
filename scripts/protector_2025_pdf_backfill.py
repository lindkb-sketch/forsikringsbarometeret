#!/usr/bin/env python3
"""Read Protector 2025 Q1/Q2 revenue directly from official interim PDF tables."""
import hashlib
import io
import json
import re
from audit_financials import DATA,audit
from build_verified_feed import build
from publish_geographic_workbooks import atomic_write
from protector_publish import download

SOURCES={
 (2025,1):'https://protectorforsikring.no/getfile.php/138843-1745427299/Documents/Investor%20Relation/Interim%20Reports/2025%20Interim%20Report%20Q1.pdf',
 (2025,2):'https://storage.mfn.se/c/aHR0cHM6Ly9hcGkzLm9zbG8ub3Nsb2JvcnMubm8vdjEvbmV3c3JlYWRlci9hdHRhY2htZW50P21lc3NhZ2VJZD02NTEwNjcmYXR0YWNobWVudElkPTMwODIxMA/interim-report-q2-2025-prot.pdf?news-id=bd7bca87-9f31-5428-af80-572d8ba4cfb9',
}
def parse(blob,year,quarter,url):
    import pdfplumber
    if not blob.startswith(b'%PDF-'):
        raise ValueError('Protector historical source is not a PDF')
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        title=' '.join((p.extract_text() or '')[:350] for p in pdf.pages[:2])
        if not re.search(r'Q'+str(quarter)+r'\b',title,re.I) or str(year) not in title:
            raise ValueError('Wrong Protector historical PDF period')
        found=[]
        for page,p in enumerate(pdf.pages,1):
            text=p.extract_text() or ''
            if not re.search(r'(?m)^Income overview\s*$',text):
                continue
            if not re.search(r'Q'+str(quarter)+r'\s+'+str(year),text):
                continue
            for line in text.splitlines():
                m=re.fullmatch(r'Insurance revenue\s+([\d,]+)(?:\s+.*)?',line.strip(),re.I)
                if m:
                    found.append((page,float(m.group(1).replace(',',''))))
        if len(found)!=1 or found[0][1]<=0:
            raise ValueError('Missing or ambiguous Protector 2025 Income overview revenue')
    page,value=found[0]
    return dict(company='Protector',year=year,quarter=quarter,scope='group',source_scope='group',
       period_type='quarter',metric='insurance_revenue',value=value,unit='MNOK',
       status='reported',source_type='official_quarterly_report',source_url=url,
       source_page=page,source_sha256=hashlib.sha256(blob).hexdigest(),
       source_document_period=f'Q{quarter} {year}',source_section='Income overview',
       source_definition='Official Protector insurance revenue, same quarter')

def run():
    data=json.loads(DATA.read_text())
    keys=('company','year','quarter','scope','period_type','metric')
    index={tuple(r[k] for k in keys):r for r in data['observations']}
    additions=[]
    for (year,quarter),url in sorted(SOURCES.items()):
        row=parse(download(url),year,quarter,url)
        prev=index.get(tuple(row[k] for k in keys))
        if prev:
            if prev['value']!=row['value']:
                raise ValueError('Protector historical PDF comparator conflicts with published data')
        else:
            additions.append(row)
    result={**data,'observations':data['observations']+additions}
    if not audit(result)['ok']:
        raise ValueError('Protector historical PDF data failed audit')
    if additions:
        atomic_write(DATA,result)
        atomic_write(DATA.parent/'verified_financial_feed.json',build(result))
    print('PROTECTOR_2025_PDF_GROWTH_COMPARATORS',len(additions),flush=True)
if __name__=='__main__':
    run()
