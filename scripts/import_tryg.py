#!/usr/bin/env python3
"""Fail-closed Tryg A/S group PDF and Norway XLSX import from paired issuer links."""
import hashlib,io,json,re,tempfile
from pathlib import Path
import pdfplumber
from audit_financials import ROOT,audit
from ingest_official_pdf import download as download_pdf,merge
from publish_geographic_workbooks import prepare,atomic_write
from build_verified_feed import build

CANDIDATES=ROOT/'data/tryg_candidates.json'
DATA=ROOT/'data/financial_observations.json'
FEED=ROOT/'data/verified_financial_feed.json'
FIELDS={'insurance_revenue':r'Insurance revenue','insurance_service_result':r'Insurance service result',
        'loss_ratio':r'Claims ratio, net of reinsurance','expense_ratio':r'Expense ratio',
        'combined_ratio':r'Combined ratio'}
NUMBER=r'-?\d[\d,]*(?:\.\d+)?'

def parse_group(blob,year,quarter,url):
    if not blob.startswith(b'%PDF-') or len(blob)>35_000_000:raise ValueError('Invalid Tryg group PDF')
    sha=hashlib.sha256(blob).hexdigest()
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages)>250:raise ValueError('Oversized Tryg report')
        candidates=[]
        for page_no,page in enumerate(pdf.pages,1):
            lines=(page.extract_text() or '').splitlines()
            for i,line in enumerate(lines):
                if line.strip()!='Income overview':continue
                header=' '.join(lines[i+1:i+4])
                if not re.search(r'Q\s*'+str(quarter)+r'\b',header,re.I) or str(year) not in header:continue
                candidates.append((page_no,lines[i+1:i+55]))
        if len(candidates)!=1:raise ValueError('Tryg group income overview missing or ambiguous')
        page_no,lines=candidates[0]
        # Q1 has 3 columns (current/prior/year); Q2-Q4 have 5 (quarter and YTD).
        column_count=5 if re.search(r'Q1-Q[234]|H1|Q1-Q3',lines[0],re.I) else 3
        if quarter>1 and column_count!=5:raise ValueError('Tryg YTD columns missing')
        if not re.search(r'Q\s*'+str(quarter)+r'\b',lines[0],re.I):raise ValueError('Quarter mismatch')
        if not re.search(r'\b'+str(year)+r'\b',lines[1]):raise ValueError('Year mismatch')
        out=[]
        for metric,label in FIELDS.items():
            pattern=r'^'+label+r'(?:a\))?\s+'+r'\s+'.join('('+NUMBER+')' for _ in range(column_count))+r'\s*$'
            found=[re.match(pattern,line.strip(),re.I) for line in lines]
            matches=[m for m in found if m]
            if len(matches)!=1:raise ValueError('Tryg group metric missing or ambiguous: '+metric)
            for period,col in [('quarter',1),('ytd',3)]:
                val=float(matches[0].group(1 if period=='quarter' else (3 if column_count==5 else 1)).replace(',',''))
                out.append(dict(company='Tryg',year=year,quarter=quarter,scope='group',
                                source_scope='group',period_type=period,metric=metric,value=val,
                                unit='percent' if metric.endswith('ratio') else 'MDKK',
                                status='reported',source_url=url,source_type='official_quarterly_report',
                                source_page=page_no,source_sha256=sha,source_section='Income overview'))
        return out

def run(pairs=None):
    if pairs is None:pairs=json.loads(CANDIDATES.read_text())['pairs']
    if not pairs:raise ValueError('No official Tryg pairs')
    latest=max((x['year'],x['quarter']) for x in pairs)
    existing=json.loads(DATA.read_text())
    for spec in sorted(pairs,key=lambda x:(x['year'],x['quarter'])):
        year,quarter=spec['year'],spec['quarter']
        if year<2026:continue
        pdf=download_pdf(spec['report_pdf_url'])
        group=parse_group(pdf,year,quarter,spec['report_pdf_url'])
        existing,_=merge(existing,group)
        wb={'workbooks':[{'company':'Tryg','year':year,'quarter':quarter,
                          'workbook_url':spec['workbook_url'],'report_pdf_url':spec['report_pdf_url'],
                          'approved':True}]}
        # Existing audited Norway observations may have different provenance metadata;
        # preserve them only when the workbook independently confirms the same value.
        try:
            existing,_,_=prepare(wb,existing)
        except ValueError as exc:
            if 'Existing value conflicts with newly parsed workbook' not in str(exc):raise
            print('TRYG_WORKBOOK_PROVENANCE_CONFLICT',year,quarter,str(exc),flush=True)
            raise
        print('TRYG_VERIFIED',year,quarter,'group',len(group),'norway',
              len([r for r in existing['observations'] if r['company']=='Tryg'
                   and r['scope']=='norway' and r['year']==year and r['quarter']==quarter]))
    for scope in ('group','norway'):
        if not any(r['company']=='Tryg' and r['scope']==scope and
                   (r['year'],r['quarter'])==latest and r['period_type']=='quarter'
                   for r in existing['observations']):
            raise ValueError('Latest Tryg report not imported: '+scope+' '+str(latest))
    if not audit(existing)['ok']:raise ValueError('Tryg audit failed')
    atomic_write(DATA,existing)
    atomic_write(FEED,build(existing))
    return latest

if __name__=='__main__':print('TRYG_LATEST',run())
