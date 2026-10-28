#!/usr/bin/env python3
"""Import explicitly reported issuer ROE/ROOF from official quarterly PDFs only.

No estimation, no investment return used as equity return. Missing labels
remain missing; only an unambiguous, period-matched report value is published.
"""
import hashlib
import io
import json
import re
import pdfplumber
from audit_financials import DATA, audit
from build_verified_feed import build
from ingest_official_pdf import download
from publish_geographic_workbooks import atomic_write

LABELS={
 'Gjensidige':(
   r'(?:annualis(?:ed|z) return on equity|return on equity,? annualis(?:ed|z))',
   'ROE annualised'),
 'Protector':(
   r'return on equity,? annualis(?:ed|z)',
   'ROE annualised'),
 'Tryg':(
   r'(?:return on own funds\s*\(ROOF\)|\bROOF\b)',
   'ROOF annualised'),
}
NUMBER=r'-?\d{1,3}(?:[.,]\d{1,2})?'

def extract(blob,company,year,quarter):
    if not blob.startswith(b'%PDF-'):raise ValueError('Not an issuer PDF')
    label,definition=LABELS[company]
    candidates=[]
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for pageno,page in enumerate(pdf.pages,1):
            text=' '.join((page.extract_text() or '').split())
            # First prefer a prose statement such as ROOF was 47.0% or
            # ROE of 34.2%; no unverified positional table columns.
            patterns=[
              r'(?:'+label+r')\s*(?:was|of|at|:|increased to|amounted to|reached)?\s*('+NUMBER+r')\s*(?:per cent|%)',
              r'(?:'+label+r')\s*(?:increased|decreased)\s+to\s*('+NUMBER+r')\s*(?:per cent|%)',
            ]
            for pattern in patterns:
                for m in re.finditer(pattern,text,re.I):
                    value=float(m.group(1).replace(',','.'))
                    if -100<=value<=200:candidates.append((pageno,value))
    distinct={round(v,3) for _,v in candidates}
    if len(distinct)!=1:
        raise ValueError(company+' explicit return missing or ambiguous: '+str(sorted(distinct)))
    pageno,value=candidates[0]
    return pageno,value,definition

def run():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    records=data['observations']
    sources=sorted({(r['company'],r['year'],r['quarter'],r['source_url'])
        for r in records if r.get('company') in LABELS and
        r.get('scope')=='group' and r.get('period_type')=='quarter'
        and r.get('metric')=='insurance_revenue' and
        r.get('source_type')=='official_quarterly_report' and r.get('year')>=2025})
    existing={(r['company'],r['year'],r['quarter'],r['scope'],r['period_type'],r['metric']):r
              for r in records}
    added=0
    for company,year,quarter,url in sources:
        k=(company,year,quarter,'group','quarter','return_on_equity')
        if k in existing:continue
        try:
            blob=download(url)
            page,value,definition=extract(blob,company,year,quarter)
        except (ValueError,OSError,TimeoutError) as error:
            print('::warning::RETURN_PDF_UNVERIFIED',company,year,quarter,str(error)[:130],flush=True)
            continue
        row=dict(company=company,year=year,quarter=quarter,scope='group',
            source_scope='group',period_type='quarter',metric='return_on_equity',
            value=value,unit='percent',status='reported',
            source_type='official_quarterly_report',source_url=url,
            source_page=page,source_sha256=hashlib.sha256(blob).hexdigest(),
            source_document_period=f'Q{quarter} {year}',source_definition=definition)
        records.append(row)
        existing[k]=row
        added+=1
        print('REPORTED_RETURN_PDF',company,year,quarter,value,definition,flush=True)
    if not audit(data)['ok']:raise ValueError('Reported returns failed audit')
    if added:
        atomic_write(DATA,data)
        atomic_write(DATA.parent/'verified_financial_feed.json',build(data))
    print('REPORTED_RETURN_PDF_ADDED',added,flush=True)

if __name__=='__main__':run()
