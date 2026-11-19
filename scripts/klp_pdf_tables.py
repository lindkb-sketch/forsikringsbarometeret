#!/usr/bin/env python3
"""Inspect REAL official KLP PDF tables; never infer or publish finance metrics.

Downloads only an approved issuer PDF, extracts page-indexed cells, and emits
a diagnostic JSON artifact. A report-specific verified mapping is still needed
before data can enter the financial feed.
"""
import argparse
import hashlib
import io
import json
import re
from import_extended_pdfs import approved, download

LABEL=re.compile(r'forsikrings|premie|erstatning|skadeprosent|gjenforsikring|kostnadsprosent|totalskadeprosent|resultat',re.I)

def table_evidence(raw,url,*,extractor=None):
    if not approved(url,'KLP Skadeforsikring') or not isinstance(raw,bytes) or not raw.startswith(b'%PDF-'):
        raise ValueError('Unapproved KLP PDF or invalid bytes')
    if extractor is None:
        import pdfplumber
        def extractor(blob):
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                if not 1<=len(pdf.pages)<=500:raise ValueError('Unexpected page count')
                for page_no,page in enumerate(pdf.pages,1):
                    yield page_no,page.extract_tables() or []
    evidence=[]
    for page,tables in extractor(raw):
        if type(page)!=int or page<1:raise ValueError('Invalid PDF page')
        for table_no,table in enumerate(tables,1):
            if not isinstance(table,list):continue
            for row_no,row in enumerate(table,1):
                if not isinstance(row,(list,tuple)):continue
                cells=[' '.join(str(v or '').split())[:250] for v in row]
                if any(LABEL.search(cell) for cell in cells):
                    evidence.append({'page':page,'table':table_no,'row':row_no,'cells':cells})
    return {'company':'KLP Skadeforsikring','source_url':url,
            'source_sha256':hashlib.sha256(raw).hexdigest(),
            'status':'diagnostic_table_evidence_not_verified_financials',
            'rows':evidence}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pdf-url',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    data=download(args.pdf_url,'KLP Skadeforsikring')
    result=table_evidence(data,args.pdf_url)
    from pathlib import Path
    target=Path(args.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('KLP_PDF_TABLE_EVIDENCE',len(result['rows']),result['source_sha256'])
if __name__=='__main__':main()
