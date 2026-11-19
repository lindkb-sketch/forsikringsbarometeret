#!/usr/bin/env python3
"""Live, diagnostic KLP PDF test. Never writes production financial metrics."""
import argparse
import json
from pathlib import Path
from import_extended_pdfs import download
from klp_pdf_tables import table_evidence

def audit(url, *, fetch=download, extract=table_evidence):
    raw=fetch(url,'KLP Skadeforsikring')
    evidence=extract(raw,url)
    rows=evidence.get('rows',[])
    if not rows:
        raise ValueError('No financial table rows extracted from official KLP PDF')
    labels=[str(row['cells'][0]).lower() for row in rows if row.get('cells')]
    keywords=('forsikring','premie','erstatning','gjenforsikring','skadeprosent','kostnadsprosent','totalskadeprosent')
    found=sorted(word for word in keywords if any(word in label for label in labels))
    evidence['diagnostics']={'pdf_bytes':len(raw),'financial_rows':len(rows),
                             'keyword_groups':found,'quarter_column_verified':False,
                             'hiy_ratio_reconciliation_verified':False,
                             'production_import_approved':False}
    if len(found)<2:
        raise ValueError('Insufficient relevant financial table labels for reliable mapping')
    return evidence

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',required=True)
    p.add_argument('--out',required=True)
    args=p.parse_args()
    target=Path(args.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    try:
        result=audit(args.url)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('KLP_LIVE_PDF_EVIDENCE',result['source_sha256'],
              'rows',len(result['rows']),
              'keywords',','.join(result['diagnostics']['keyword_groups']))
        print('KLP_CERTIFICATION_PENDING actual quarter column and HIÅ reconciliation')
    except Exception as exc:
        target.write_text(json.dumps({'status':'live_pdf_audit_failed',
            'source_url':args.url,'error':str(exc)[:500],
            'production_import_approved':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        raise
if __name__=='__main__':main()
