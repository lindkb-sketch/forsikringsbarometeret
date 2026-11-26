#!/usr/bin/env python3
"""Alm. Brand official PDF evidence contract and fail-closed metric extraction.

The parser accepts only a verified quarterly table with explicit quarter
column, currency, units, and page evidence. An announcement is never a PDF.
"""
import hashlib
import re
from decimal import Decimal, InvalidOperation
from import_extended_pdfs import approved, pages
from urllib.parse import urlsplit

def official_alm_pdf(url):
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.username or parts.password or parts.port not in (None,443):return False
    return approved(url,'Alm. Brand') or (parts.hostname=='attachment.news.eu.nasdaq.com' and not parts.query and not parts.fragment and bool(re.fullmatch(r'/[0-9a-f]{32}',parts.path))) or (parts.scheme=='https' and
        parts.hostname=='s29.q4cdn.com' and
        parts.path.startswith('/228553818/files/') and
        parts.path.lower().endswith('.pdf'))

METRICS=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio')
LABELS={
 'insurance_revenue':r'Insurance revenue',
 'insurance_service_result':r'Insurance service result',
 'combined_ratio':r'Combined ratio',
 'loss_ratio':r'Claims ratio',
 'expense_ratio':r'Expense ratio',
}
def numeric(value):
    if isinstance(value,bool):raise ValueError('Invalid number')
    try:result=Decimal(str(value).replace(',',''))
    except (InvalidOperation,TypeError) as exc:raise ValueError('Invalid number') from exc
    if not result.is_finite():raise ValueError('Non-finite number')
    return float(result)

def extract_table(raw,url,year,quarter,table_rows,*,currency='DKK',unit='million'):
    """Require page-indexed table rows supplied by a verified PDF table extractor.

    table_rows entries: {page, label, period, value, unit}. A separate caller
    must establish correct source document period and group reporting scope.
    """
    if not official_alm_pdf(url):
        raise ValueError('Unapproved issuer PDF URL')
    if not isinstance(raw,bytes) or not raw.startswith(b'%PDF-'):
        raise ValueError('Not PDF bytes')
    if type(year)!=int or type(quarter)!=int or year<2020 or quarter not in (1,2,3,4):
        raise ValueError('Invalid report period')
    if currency!='DKK' or unit!='million':
        raise ValueError('Unexpected currency or units')
    if not isinstance(table_rows,list) or not table_rows:
        raise ValueError('No verified PDF table rows')
    selected={}
    for row in table_rows:
        if row.get('period')!=f'Q{quarter} {year}':
            continue
        label=str(row.get('label','')).strip()
        matches=[metric for metric,pattern in LABELS.items() if re.fullmatch(pattern,label,re.I)]
        if not matches:continue
        if row.get('unit')!=('%' if matches[0] in ('combined_ratio','loss_ratio','expense_ratio') else 'DKK million'):
            raise ValueError('Incompatible metric units')
        if type(row.get('page'))!=int or row['page']<1:
            raise ValueError('Missing PDF page provenance')
        metric=matches[0]
        if metric in selected:
            raise ValueError('Ambiguous duplicate metric row: '+metric)
        selected[metric]=(numeric(row.get('value')),row['page'])
    if set(selected)!=set(METRICS):
        raise ValueError('Incomplete isolated-quarter PDF metrics: '+str(sorted(set(METRICS)-set(selected))))
    values={metric:selected[metric][0] for metric in METRICS}
    if values['insurance_revenue']<=0 or not 0<=values['combined_ratio']<=200:
        raise ValueError('Implausible PDF metrics')
    # No assumption that service result equals revenue*(1-combined ratio):
    # source accounting may include rounding and issuer-specific adjustments.
    return {'company':'Alm. Brand','year':year,'quarter':quarter,'currency':currency,
            'scope':'group','source_type':'official_quarterly_report',
            'source_url':url,'source_sha256':hashlib.sha256(raw).hexdigest(),
            'source_pages':{k:selected[k][1] for k in METRICS},
            'metrics':values,'status':'pdf_table_extracted_pending_independent_reconciliation',
            'unit':'DKK million for financial amounts; percent for ratios'}

def inspect_report(raw,url):
    """Inspect actual PDF pages, returning evidence candidates without metrics."""
    if not official_alm_pdf(url) or not raw.startswith(b'%PDF-'):
        raise ValueError('Unapproved or invalid PDF')
    result=[]
    for page_number,text in enumerate(pages(raw),1):
        matches=sorted(k for k,pattern in LABELS.items() if re.search(pattern,text,re.I))
        if matches:result.append({'page':page_number,'metric_labels':matches})
    return {'company':'Alm. Brand','source_url':url,
            'source_sha256':hashlib.sha256(raw).hexdigest(),
            'pages':result,'status':'requires_verified_quarter_column_mapping'}
