#!/usr/bin/env python3
"""Import explicitly reported quarter-end group solvency from official issuer PDFs.

An absent or ambiguous explicitly labelled percentage is not populated.
Never substitute a subsidiary's capital adequacy for group solvency.
"""
import hashlib
import io
import json
import re
import pdfplumber
from audit_financials import DATA,audit
from ingest_official_pdf import download
from publish_geographic_workbooks import atomic_write

COMPANIES=('Gjensidige','Tryg','Protector','Sampo')
def extract(blob,company,year,quarter):
    if not blob.startswith(b'%PDF-'):raise ValueError('Not an official PDF')
    candidates=[]
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_num,page in enumerate(pdf.pages,1):
            text=' '.join((page.extract_text() or '').split())
            if not text:continue
            if company=='Gjensidige':
                # The group table uses the approved partial internal model.
                # Exclude the separate ASA and pension company ratios.
                if not re.search(r'Gjensidige Forsikring Group',text,re.I):continue
                groups=re.split(r'Gjensidige Forsikring ASA|Gjensidige Pensjonsforsikring',text,flags=re.I)
                group=groups[0]
                matches=list(re.finditer(r'Solvency ratio\\s*(?:\\d+)?\\s*%\\s*([12]\\d{2}[.,]\\d)',group,re.I))
                for hit in matches:
                    value=float(hit.group(1).replace(',','.'))
                    if 100<=value<=400:candidates.append((page_num,value))
                continue
            if company=='Tryg':
                patterns=[
                    r'solvency ratio was\s*(\d{2,3}(?:[.,]\d+)?)\s*%\s*at the end of Q'+str(quarter)+r'\s*'+str(year),
                    r'(?:reported )?solvency ratio at the end of Q'+str(quarter)+r'\s*'+str(year)+r' was\s*(\d{2,3}(?:[.,]\d+)?)\s*%'
                ]
            elif company=='Sampo':
                if not re.search(r'(?:Q\s*'+str(quarter)+r'|half.year|H1)\s*'+str(year),text,re.I):continue
                patterns=[
                    r'\bSolvency\s*II\s*ratio\s*(?:was|of|:)?\s*(\d{2,3}(?:[.,]\d+)?)\s*%',
                    r'\bGroup\s*solvency\s*ratio\s*(?:was|of|:)?\s*(\d{2,3}(?:[.,]\d+)?)\s*%'
                ]
            else:
                # Label and reported quarter explicitly visible on the page;
                # take the first value after the current ratio label, not a
                # parenthesized comparative or SCR amount.
                if not re.search(r'Q\s*'+str(quarter)+r'\s*'+str(year),text,re.I):continue
                patterns=[r'\b(?:solvency ratio|SCR[ -]ratio)\s*(?:was|of|:)?\s*(\d{2,3}(?:[.,]\d+)?)\s*%']
            for pattern in patterns:
                for hit in re.finditer(pattern,text,re.I):
                    value=float(hit.group(1).replace(',','.'))
                    if 100<=value<=400:candidates.append((page_num,value))
    values={v for _,v in candidates}
    if len(values)!=1:raise ValueError('Missing or ambiguous quarter-specific solvency '+str(sorted(values)))
    return candidates[0]

def run():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    rows=data['observations']
    count=0
    for company in COMPANIES:
        sources=[r for r in rows if r.get('company')==company and
                 r.get('scope')=='group' and r.get('metric')=='insurance_revenue'
                 and r.get('period_type') in ('quarter','ytd')
                 and r.get('source_type')=='official_quarterly_report'
                 and str(r.get('source_url','')).startswith('https://')]
        if not sources:continue
        newest=max((r['year'],r['quarter']) for r in sources)
        # Backfill all 2026 quarters plus same-quarter prior-year observations.
        periods=sorted({(r['year'],r['quarter']) for r in sources
                        if r['year']>=2025 and
                        (r['year']==2026 or (r['year'],r['quarter'])<=newest)})
        for year,quarter in periods:
            if any(r.get('company')==company and r.get('scope')=='group'
                   and (r.get('year'),r.get('quarter'))==(year,quarter)
                   and r.get('metric')=='solvency_ratio' for r in rows):continue
            available=[r for r in sources if (r['year'],r['quarter'])==(year,quarter)]
            source=next((r for r in available if str(year) in r['source_url']),available[0])
            try:
                blob=download(source['source_url'])
                page,value=extract(blob,company,year,quarter)
            except Exception as exc:
                print('::warning::SOLVENCY_PDF_UNVERIFIED',company,year,quarter,str(exc)[:180],flush=True)
                continue
            rows.append(dict(company=company,year=year,quarter=quarter,scope='group',
                 source_scope='group',period_type='quarter',metric='solvency_ratio',
                 value=value,unit='percent',status='reported',
                 source_type='official_quarterly_report',source_url=source['source_url'],
                 source_page=page,source_sha256=hashlib.sha256(blob).hexdigest(),
                 source_document_period=f'Q{quarter} {year}',
                 source_definition='Reported quarter-end regulatory group solvency ratio'))
            count+=1
            print('OFFICIAL_GROUP_SOLVENCY',company,year,quarter,value,page,flush=True)
    if not audit(data)['ok']:raise ValueError('Solvency source audit failed')
    if count:atomic_write(DATA,data)
    print('SOLVENCY_QTR_PDF_ADDED',count,flush=True)
if __name__=='__main__':run()
