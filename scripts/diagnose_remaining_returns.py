#!/usr/bin/env python3
"""Report a bounded layout diagnostic for five currently unrecovered issuer ROE/ROOF rows.

Source documents are original fingerprinted issuer PDFs recorded in production.
Diagnostic only: never publishes or copies numerical values.
"""
import hashlib
import io
import json
import re
from pathlib import Path
import pdfplumber
from ingest_official_pdf import download

ROOT=Path(__file__).resolve().parents[1]
TARGETS={('Fremtind',2025,3),('Fremtind',2025,4),
         ('Gjensidige',2025,4),('Tryg',2025,4),('Tryg',2026,3)}
PATTERN=re.compile(r'egenkapitalavkastning|own funds|\bROOF\b|return on equity|equity return|annualis',re.I)

def examine(row,fetch=download):
    result={'company':row['company'],'year':row['year'],'quarter':row['quarter'],
            'source_url':row['source_url'],'source_page':row.get('source_page')}
    try:
        blob=fetch(row['source_url'])
        digest=hashlib.sha256(blob).hexdigest()
        if digest!=row.get('source_sha256') or not blob.startswith(b'%PDF-'):
            raise ValueError('Original registered PDF source fingerprint does not match')
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            page=int(row['source_page'])
            if page<1 or page>len(pdf.pages):raise ValueError('Registered source page outside PDF')
            data=pdf.pages[page-1].extract_text() or ''
            lines=data.splitlines()
            matches=[i for i,line in enumerate(lines) if PATTERN.search(line)]
            selected=matches[:8]
            result['page_count']=len(pdf.pages)
            result['matches']=[{'line':i+1,'context':' | '.join(lines[max(0,i-1):min(len(lines),i+3)])[:420]}
                               for i in selected]
            result['page_opening']=' | '.join(lines[:5])[:300]
            result['status']='verified_original_pdf'
    except Exception as exc:
        result['status']='source_unavailable_or_invalid'
        result['error']=type(exc).__name__+': '+str(exc)[:250]
    return result

def main():
    rows=json.loads((ROOT/'data/financial_observations.json').read_text())['observations']
    selected=[r for r in rows if
              (r.get('company'),r.get('year'),r.get('quarter')) in TARGETS
              and r.get('scope')=='group' and r.get('period_type')=='quarter'
              and r.get('metric')=='return_on_equity']
    if len(selected)!=len(TARGETS):raise ValueError('Expected five unique original source rows')
    results=[examine(r) for r in selected]
    print('ORIGINAL_RETURN_LAYOUTS',json.dumps(results,ensure_ascii=False))
    Path(ROOT/'data/remaining_return_source_diagnostics.json').write_text(
        json.dumps({'results':results,'diagnostic_only':True},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
