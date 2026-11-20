#!/usr/bin/env python3
"""Real Q3 issuer-PDF provenance and metric reconciliation, strictly diagnostic.

Download known issuer reports and discovered presentations, check bytes, issuer,
period, SHA256, source pages, then extract only unambiguous label/value lines.
Never use previously published numbers as extracted PDF evidence. Never publish
values or assert dual-document completeness when either document is missing.
"""
import hashlib
import io
import json
import re
from collections import defaultdict
from pathlib import Path

from verify_nine_document_bytes import COMPANIES, approved, download, period_matches, ISSUER_TEXT

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'data/nine_document_metric_reconciliation.json'
CORE=('insurance_revenue','insurance_service_result','combined_ratio',
      'loss_ratio','expense_ratio','solvency_ratio','return_on_equity')
LABELS={
 'insurance_revenue':(r'insurance (?:service )?revenue',r'inntekter fra forsikringstjenester',r'forsikringsinntekter'),
 'insurance_service_result':(r'insurance service result',r'resultat fra forsikringstjenester'),
 'combined_ratio':(r'combined ratio',r'kombinert(?:prosent| ratio)'),
 'loss_ratio':(r'loss ratio',r'skadeprosent'),
 'expense_ratio':(r'expense ratio',r'kostnadsprosent'),
 'solvency_ratio':(r'solvency (?:capital )?ratio',r'solvens(?:kapital)?dekning',r'solvency ii ratio'),
 'return_on_equity':(r'return on equity',r'egenkapitalavkastning'),
}
NUMBER=re.compile(r'(?<![A-Za-z0-9])[-+]?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d+)?(?![A-Za-z0-9])|(?<![A-Za-z0-9])[-+]?\d+(?:[,.]\d+)?(?![A-Za-z0-9])')

def parse_number(token):
    s=token.replace(' ','').replace('\u00a0','')
    if ',' in s and '.' in s:
        s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
    elif ',' in s:s=s.replace(',','.')
    elif s.count('.')==1 and len(s.split('.')[1])==3:s=s.replace('.','')
    return float(s)

def extract_unambiguous(lines,metric,expected=None):
    """Return value only for a single labelled value; never guess a table column.

    expected is deliberately NOT used to choose among ambiguous values.
    """
    labels=LABELS.get(metric,())
    matches=[]
    for line in lines:
        if not any(re.search(p,line,re.I) for p in labels):continue
        # A label must be followed by exactly one numeric field on this line.
        # Many official tables have multiple period columns; these are ambiguous.
        label_end=min((m.end() for p in labels if (m:=re.search(p,line,re.I))),default=0)
        tail=line[label_end:].strip(' :–—\t')
        numbers=[parse_number(x.group()) for x in NUMBER.finditer(tail)]
        if len(numbers)==1:matches.append(numbers[0])
    unique=sorted(set(matches))
    return unique[0] if len(unique)==1 else None

def discover_presentation_metrics(pages,year,quarter):
    """Extract only single-value Q3-labelled GROUP presentation pages.

    No inference from other slides, historical columns, or group/segment ambiguity.
    This is independent of previously committed report values.
    """
    evidence=[]
    for page_number,page in pages:
        lines=page.splitlines()
        if not period_matches(page,year,quarter):continue
        if not re.search(r'\\b(?:group|konsern)\\b',page,re.I):continue
        if re.search(r'\\b(?:norway only|norge alene|segment only)\\b',page,re.I):continue
        for metric in CORE:
            value=extract_unambiguous(lines,metric)
            if value is None:continue
            if metric in ('insurance_revenue','insurance_service_result'):
                # Currency/scale is not unambiguously identifiable on arbitrary slides.
                continue
            evidence.append({'metric':metric,'scope':'group','period_type':'quarter',
                'unit':'percent','source_page':page_number,
                'document_type':'results_presentation','value':value,
                'status':'extracted_unambiguous','committed_value':None,
                'committed_value_matches':None,'extraction_method':'single_label_period_and_group_page'})
    return evidence

def source_documents(feed,extended,candidates,year,quarter):
    docs=defaultdict(dict)
    rows=feed.get('observations',[])
    for x in rows:
        if x.get('company') not in COMPANIES or (x.get('year'),x.get('quarter'))!=(year,quarter):continue
        if x.get('source_type')!='official_quarterly_report':continue
        company,url=x['company'],x.get('source_url','')
        if not approved(company,url):continue
        doc=docs[company].setdefault(('quarterly_report',url),{
            'company':company,'document_type':'quarterly_report','url':url,
            'expected_hashes':set(),'observations':[]})
        if x.get('source_sha256'):doc['expected_hashes'].add(x['source_sha256'])
        doc['observations'].append(x)
    for company,x in extended.get('insurers',{}).items():
        if company not in COMPANIES or (x.get('year'),x.get('quarter'))!=(year,quarter):continue
        for kind,record in [('quarterly_report',x),('results_presentation',x.get('presentation_evidence',{}))]:
            url=record.get('source_url','')
            if not approved(company,url):continue
            if kind=='quarterly_report' and record.get('source_type') not in ('official_quarterly_report',):continue
            if kind=='results_presentation' and record.get('source_type')!='official_results_presentation':continue
            doc=docs[company].setdefault((kind,url),{'company':company,'document_type':kind,
                'url':url,'expected_hashes':set(),'observations':[]})
            if record.get('source_sha256'):doc['expected_hashes'].add(record['source_sha256'])
            if kind=='results_presentation':
                for metric,value in record.get('metrics',{}).items():
                    if metric in CORE:
                        doc['observations'].append({'metric':metric,'value':value,
                            'source_page':record.get('source_page'),'scope':record.get('scope','group'),
                            'period_type':'quarter','unit':'percent' if metric in ('solvency_ratio','return_on_equity','combined_ratio','loss_ratio','expense_ratio') else record.get('currency','unknown')})
    for x in candidates.get('candidates',[]):
        company,kind,url=x.get('company'),x.get('document_type'),x.get('document_url','')
        if company not in COMPANIES or kind not in ('quarterly_report','results_presentation'):continue
        if not approved(company,url):continue
        label=x.get('link_text','')+' '+url
        if not period_matches(label,year,quarter):continue
        docs[company].setdefault((kind,url),{'company':company,'document_type':kind,
            'url':url,'expected_hashes':set(),'observations':[]})
    return docs

def reconcile_extracted(records,tolerance=0.05):
    """Compare independently extracted same-metric, same-scope, same-period values."""
    grouped=defaultdict(dict)
    for r in records:
        if r.get('status')!='extracted_unambiguous':continue
        key=(r['metric'],r['scope'],r['period_type'],r.get('unit','unknown'))
        grouped[key].setdefault(r['document_type'],[]).append(r['value'])
    results=[]
    for key,by_type in sorted(grouped.items()):
        if not {'quarterly_report','results_presentation'}.issubset(by_type):continue
        report=sorted(set(by_type['quarterly_report']))
        presentation=sorted(set(by_type['results_presentation']))
        if len(report)!=1 or len(presentation)!=1:
            status='ambiguous'
        else:
            status='match' if abs(report[0]-presentation[0])<=tolerance else 'conflict'
        results.append({'metric':key[0],'scope':key[1],'period_type':key[2],'unit':key[3],
                        'report_values':report,'presentation_values':presentation,'status':status})
    return results

def verify_document(doc,year,quarter):
    company,url=doc['company'],doc['url']
    raw,final=download(company,url)
    if not raw.startswith(b'%PDF-'):raise ValueError('Not PDF bytes')
    digest=hashlib.sha256(raw).hexdigest()
    if doc['expected_hashes'] and digest not in doc['expected_hashes']:
        raise ValueError('Source SHA256 differs from committed financial provenance')
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        opening='\n'.join((p.extract_text() or '') for p in pdf.pages[:min(len(pdf.pages),12)])
        if not re.search(ISSUER_TEXT[company],opening,re.I):raise ValueError('Issuer not confirmed')
        if not period_matches(opening,year,quarter):raise ValueError('Quarter not confirmed')
        page_text={}
        for row in doc['observations']:
            p=row.get('source_page')
            if type(p) is int and 1<=p<=len(pdf.pages):
                page_text[p]=pdf.pages[p-1].extract_text() or ''
        # Presentation metric extraction must be anchored to a real source page.
        extracted=[]
        for row in doc['observations']:
            p=row.get('source_page')
            if p not in page_text:continue
            metric=row.get('metric')
            if metric not in CORE:continue
            val=extract_unambiguous(page_text[p].splitlines(),metric)
            extracted.append({'metric':metric,'scope':row.get('scope','group'),
                'period_type':row.get('period_type','quarter'),
                'unit':row.get('unit','percent' if metric in ('solvency_ratio','return_on_equity','combined_ratio','loss_ratio','expense_ratio') else 'unknown'),
                'source_page':p,
                'document_type':doc['document_type'],'value':val,
                'status':'extracted_unambiguous' if val is not None else 'ambiguous_or_not_found',
                'committed_value':row.get('value'),
                'committed_value_matches':val is not None and abs(val-row.get('value',float('inf')))<0.05})
        if doc['document_type']=='results_presentation':
            pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
            extracted.extend(discover_presentation_metrics(pages,year,quarter))
    return {'company':company,'document_type':doc['document_type'],'url':final,
            'source_sha256':digest,'status':'verified_pdf_bytes','metric_evidence':extracted}

def run(year=2026,quarter=3):
    def load(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
    docs=source_documents(load('data/verified_financial_feed.json'),
        load('data/extended_insurer_financials.json'),load('data/report_candidates.json'),year,quarter)
    output={'schema_version':1,'year':year,'quarter':quarter,
            'metrics_published':False,'investor_use_approved':False,'companies':[]}
    for company in COMPANIES:
        checked=[]
        for doc in list(docs[company].values())[:12]:
            try:checked.append(verify_document(doc,year,quarter))
            except Exception as exc:
                checked.append({'company':company,'document_type':doc['document_type'],
                    'url':doc['url'],'status':'unverified','error':type(exc).__name__+': '+str(exc)[:200]})
        types={x['document_type'] for x in checked if x['status']=='verified_pdf_bytes'}
        metrics=[dict(row,source_sha256=x['source_sha256']) for x in checked
                 if x['status']=='verified_pdf_bytes' for row in x['metric_evidence']]
        matches=reconcile_extracted(metrics)
        conflicts=[m for m in matches if m['status']!='match']
        verified={'quarterly_report','results_presentation'}.issubset(types)
        # Even matching overlapping metrics do not establish full extraction of all KPIs.
        output['companies'].append({'company':company,'documents':checked,
            'report_verified':'quarterly_report' in types,
            'presentation_verified':'results_presentation' in types,
            'both_documents_verified':verified,'metric_evidence':metrics,
            'cross_document_matches':matches,'conflicts':conflicts,
            'metric_extraction_status':'partial_reconciliation' if verified and matches and not conflicts
                                        else 'not_certified'})
    output['all_nine_dual_document_verified']=all(c['both_documents_verified'] for c in output['companies'])
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('NINE_DOCUMENT_METRIC_AUDIT',json.dumps({x['company']:{
        'report':x['report_verified'],'presentation':x['presentation_verified'],
        'matched_metrics':len(x['cross_document_matches']),'conflicts':len(x['conflicts'])}
        for x in output['companies']},ensure_ascii=False))
    return output

if __name__=='__main__':run()
