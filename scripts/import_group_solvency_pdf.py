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

COMPANIES=('Tryg','Protector','Sampo','Gjensidige')
def extract(blob,company,year,quarter):
    if not blob.startswith(b'%PDF-'):raise ValueError('Not an official PDF')
    candidates=[]
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if company=='Gjensidige':
            # A comparative in a newer PDF is not a prior-year solvency
            # observation. Verify issuer, original quarter and original year.
            head=' '.join((p.extract_text() or '') for p in pdf.pages[:2]).lower()
            quarter_words=('first','second','third','fourth')
            period_ok=bool(re.search(r'\bq\s*'+str(quarter)+r'\b|\b'+
                str(quarter)+r'(?:st|nd|rd|th)\s+quarter\b|\b'+
                quarter_words[quarter-1]+r'\s+quarter\b',head))
            if 'gjensidige' not in head or str(year) not in head or not period_ok:
                raise ValueError('Gjensidige PDF cover does not verify the requested quarter and year')
        for page_num,page in enumerate(pdf.pages,1):
            text=' '.join((page.extract_text() or '').split())
            if not text:continue
            if company=='Gjensidige':
                # Approved GROUP partial internal model, not own PIM or
                # solvency for Gjensidige Forsikring ASA / pension.
                patterns=[
                    r'\bApproved\s+Partial\s+Internal\s+Model'
                    r'(?:\s*[:\-]?\s*(?:[¹²³]|\d{1,2})\s*[:\-]?)?'
                    r'\s*[:\-]?\s*(\d{3}(?:[.,]\d+)?)\s*(?:per\s+cent|%)'
                ]
            elif company=='Tryg':
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
        candidates=[r for r in rows if r.get('company')==company and
            r.get('scope')=='group' and r.get('metric')=='insurance_revenue'
            and r.get('period_type') in ('quarter','ytd')]
        if not candidates:continue
        year,quarter=max((r['year'],r['quarter']) for r in candidates)
        # Both current and same quarter last year are needed for comparison.
        for target_year in (year-1,year):
            if any(r.get('company')==company and r.get('scope')=='group'
                   and (r.get('year'),r.get('quarter'))==(target_year,quarter)
                   and r.get('metric')=='solvency_ratio' for r in rows):continue
            sources=[r for r in candidates if (r['year'],r['quarter'])==(target_year,quarter)
                     and r.get('source_type')=='official_quarterly_report'
                     and str(r.get('source_url','')).startswith('https://')]
            if not sources:continue
            # A Gjensidige revenue comparative can cite the current-year
            # report. Discover the *original* prior-year report for solvency.
            if company=='Gjensidige' and target_year!=year:
                from gjensidige_publish import discover_quarter
                try:
                    approved=discover_quarter(quarter,target_year)
                except Exception as exc:
                    print('::warning::SOLVENCY_PDF_DISCOVERY',company,target_year,quarter,str(exc)[:180],flush=True)
                    continue
                if not approved:
                    print('::warning::SOLVENCY_PDF_DISCOVERY no official historical report',target_year,quarter,flush=True)
                    continue
                selected_url=approved
            else:
                source=next((r for r in sources if str(target_year) in r['source_url']),sources[0])
                selected_url=source['source_url']
            try:
                blob=download(selected_url)
                page,value=extract(blob,company,target_year,quarter)
            except Exception as exc:
                print('::warning::SOLVENCY_PDF_UNVERIFIED',company,target_year,quarter,str(exc)[:180],flush=True)
                continue
            rows.append(dict(company=company,year=target_year,quarter=quarter,scope='group',
                 source_scope='group',period_type='quarter',metric='solvency_ratio',
                 value=value,unit='percent',status='reported',
                 source_type='official_quarterly_report',source_url=selected_url,
                 source_page=page,source_sha256=hashlib.sha256(blob).hexdigest(),
                 source_document_period=f'Q{quarter} {target_year}',
                 source_definition='Reported quarter-end Group solvency ratio'))
            count+=1
            print('OFFICIAL_GROUP_SOLVENCY',company,target_year,quarter,value,page,flush=True)
    if not audit(data)['ok']:raise ValueError('Solvency source audit failed')
    if count:atomic_write(DATA,data)
    print('SOLVENCY_QTR_PDF_ADDED',count,flush=True)
if __name__=='__main__':run()
